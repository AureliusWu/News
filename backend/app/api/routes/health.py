from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
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


def _build_health_payload(connected: bool, status: str) -> dict[str, object]:
    return {
        "status": status,
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "environment": settings.app_env,
        "database_connected": connected,
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


@router.get("/health", response_model=HealthResponse)
async def root_health() -> HealthResponse:
    connected = await db_health()
    payload = _build_health_payload(connected, "healthy" if connected else "degraded")
    return HealthResponse(**payload)


@router.get("/ready")
async def ready_health():
    connected = await db_health()
    payload = _build_health_payload(connected, "ready" if connected else "not_ready")
    if connected:
        return HealthResponse(**payload)

    return JSONResponse(status_code=503, content=payload)


@router.get("/api/v1/health", response_model=HealthResponse)
async def api_health() -> HealthResponse:
    return await root_health()
