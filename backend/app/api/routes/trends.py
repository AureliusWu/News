from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.services.event_trends import build_trends
from app.services.native_events import native_bundle

router = APIRouter(prefix="/api/v1", tags=["event-trends"])


@router.get("/trends")
async def trends(db: AsyncSession = Depends(get_db)):
    bundle = await native_bundle(db)
    try:
        return build_trends(bundle["events"], bundle["news"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="Event trend policy unavailable", headers={"Retry-After": "5"}) from exc
