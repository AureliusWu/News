from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.core.db import db_health


router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    app_name: str
    app_version: str
    environment: str
    database_connected: bool
    checked_at: datetime


@router.get("/health", response_model=HealthResponse)
async def root_health() -> HealthResponse:
    connected = await db_health()
    return HealthResponse(
        status="healthy" if connected else "degraded",
        app_name=settings.app_name,
        app_version=settings.app_version,
        environment=settings.app_env,
        database_connected=connected,
        checked_at=datetime.now(timezone.utc),
    )


@router.get("/api/v1/health", response_model=HealthResponse)
async def api_health() -> HealthResponse:
    return await root_health()
