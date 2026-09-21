from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, field_serializer


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    name: str
    publisher: str
    homepage: str
    country: str
    region: str
    language: str
    category: str
    source_type: str
    health_status: str
    enabled: bool


class ArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    summary: str | None
    url: str
    image_url: str | None
    source: SourceResponse
    region: str
    language: str
    category: str
    published_at: datetime

    @field_serializer("published_at")
    def utc_date(self, value):
        return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)).isoformat().replace("+00:00", "Z")


class NewsListResponse(BaseModel):
    items: list[ArticleResponse]
    next_cursor: str | None = None
    has_more: bool = False


class MetaResponse(BaseModel):
    version: str
    regions: list[str]
    categories: list[str]
    languages: list[str]
    source_count: int
    article_count: int
    last_sync_at: str | None