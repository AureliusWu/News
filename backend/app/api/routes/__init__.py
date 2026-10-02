from fastapi import APIRouter

from app.api.routes import events, health, news, trends

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(news.router)
api_router.include_router(events.router)
api_router.include_router(trends.router)
