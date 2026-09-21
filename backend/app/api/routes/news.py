from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from app.core.config import settings
from app.core.db import get_db
from app.models import Article, Source, SyncState, utcnow
from app.schemas import ArticleResponse, MetaResponse, NewsListResponse, SourceResponse
from app.services.cursor import decode_cursor, encode_cursor

router = APIRouter(prefix="/api/v1")
DB = Annotated[AsyncSession, Depends(get_db)]


def article_query():
    return select(Article).join(Article.source).options(contains_eager(Article.source)).where(Source.enabled.is_(True))


@router.get("/news", response_model=NewsListResponse)
async def list_news(db: DB, response: Response, limit: int = Query(30, ge=1, le=100), cursor: str | None = None,
                    region: str | None = None, category: str | None = None, language: str | None = None,
                    source: str | None = None, q: str | None = Query(None, max_length=200)):
    stmt = article_query().order_by(Article.published_at.desc(), Article.id.desc())
    for column, value in ((Article.region, region), (Article.category, category), (Article.language, language), (Source.slug, source)):
        if value:
            stmt = stmt.where(column == value)
    if q and q.strip():
        pattern = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        stmt = stmt.where(or_(Article.title.ilike(pattern, escape="\\"), Article.summary.ilike(pattern, escape="\\")))
    if cursor is not None:
        try:
            dt, item_id = decode_cursor(cursor)
        except ValueError:
            raise HTTPException(400, "Invalid cursor") from None
        stmt = stmt.where(or_(Article.published_at < dt, and_(Article.published_at == dt, Article.id < item_id)))
    rows = (await db.scalars(stmt.limit(limit + 1))).all()
    has_more = len(rows) > limit
    items = rows[:limit]
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-News-Generated-At"] = utcnow().isoformat()
    return NewsListResponse(items=[ArticleResponse.model_validate(item) for item in items], has_more=has_more,
        next_cursor=encode_cursor(items[-1].published_at, items[-1].id) if has_more else None)


@router.get("/sources", response_model=list[SourceResponse])
async def list_sources(db: DB, enabled: bool = True):
    return (await db.scalars(select(Source).where(Source.enabled == enabled).order_by(Source.priority, Source.name))).all()


@router.get("/news/{news_id}", response_model=ArticleResponse)
async def get_news_detail(news_id: int, db: DB):
    item = await db.scalar(article_query().where(Article.id == news_id))
    if item is None:
        raise HTTPException(404, "News not found")
    return ArticleResponse.model_validate(item)


@router.get("/meta", response_model=MetaResponse)
async def get_meta(db: DB):
    sources = (await db.scalars(select(Source).where(Source.enabled.is_(True)))).all()
    count = await db.scalar(select(func.count(Article.id)).join(Source).where(Source.enabled.is_(True)))
    sync = await db.get(SyncState, "worker:last_sync_at")
    return MetaResponse(version=settings.app_version, regions=sorted({s.region for s in sources}),
        categories=sorted({s.category for s in sources}), languages=sorted({s.language for s in sources}),
        source_count=len(sources), article_count=count or 0, last_sync_at=sync.value if sync else None)