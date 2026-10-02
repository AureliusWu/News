"""Native event API. Missing configuration is 503, never a static-site fallback."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.services.native_events import EVENT, NativeEventsUnavailable, native_asset, native_bundle

router = APIRouter(prefix="/api/v1", tags=["events"])
DB = Annotated[AsyncSession, Depends(get_db)]


def _unavailable(error):
    return HTTPException(status_code=503, detail=str(error), headers={"Retry-After": "5", "Cache-Control": "no-store"})


async def _current(db):
    try:
        return await native_bundle(db)
    except NativeEventsUnavailable as error:
        raise _unavailable(error) from error


@router.get("/snapshot")
async def snapshot(db: DB):
    value = (await _current(db))["news"]
    return JSONResponse(value, headers={"Cache-Control": "no-store", "X-News-Generated-At": value["generated_at"]})


@router.get("/events")
async def events(db: DB):
    return JSONResponse((await _current(db))["events"], headers={"Cache-Control": "no-store"})


@router.get("/events/{event_id}")
async def event_detail(event_id: str, db: DB):
    if not EVENT.fullmatch(event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    bundle = await _current(db)
    canonical = bundle["events"].get("aliases", {}).get(event_id, event_id)
    event = next((row for row in bundle["events"]["events"] if row["event_id"] == canonical), None)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found in the current publication window")
    ids = set(event["article_ids"])
    value = {key: bundle["news"][key] for key in ("snapshot_id", "generated_at", "content_sha256")}
    value.update(requested_event_id=event_id, canonical_event_id=canonical, event=event,
        articles=sorted((row for row in bundle["news"]["articles"] if row["article_id"] in ids), key=lambda row: (row["published_at"], row["article_id"])))
    return JSONResponse(value, headers={"Cache-Control": "no-store"})


@router.get("/snapshots/{snapshot_id}/{name}")
async def versioned_asset(snapshot_id: str, name: str):
    try:
        value = await native_asset(snapshot_id, name)
    except NativeEventsUnavailable as error:
        raise _unavailable(error) from error
    if value is None:
        raise HTTPException(status_code=404, detail="Event generation or report not retained")
    return JSONResponse(value, headers={"Cache-Control": "no-store"})
