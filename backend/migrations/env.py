from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
if ROOT_PATH not in sys.path:
    sys.path.append(ROOT_PATH)

from app.core.config import settings

if context.config.config_file_name is not None:
    fileConfig(context.config.config_file_name)


def run_migrations_offline() -> None:
    context.configure(
        url=settings.db_dsn,
        target_metadata=None,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_async_engine(settings.db_dsn, poolclass=pool.NullPool)

    async def do_run_migrations(connection) -> None:
        context.configure(connection=connection, target_metadata=None, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()

    async def run_async() -> None:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
        await connectable.dispose()

    asyncio.run(run_async())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
