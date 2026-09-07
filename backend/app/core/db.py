from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


DATABASE_URL = settings.db_dsn
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def db_health() -> bool:
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
