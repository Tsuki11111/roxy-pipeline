from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


@asynccontextmanager
async def task_session() -> AsyncIterator[AsyncSession]:
    """One engine per Celery task; NullPool avoids loop-bound connections."""
    settings = get_settings()
    sqlite = settings.database_url.startswith("sqlite")
    if sqlite:
        raw_path = settings.database_url.split(":///", 1)[-1]
        if raw_path not in {":memory:", ""} and not raw_path.startswith("file:"):
            Path(raw_path).parent.mkdir(parents=True, exist_ok=True)

    engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        **( {"connect_args": {"timeout": 30}} if sqlite else {}),
    )
    if sqlite:

        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    try:
        async with session_factory() as session:
            yield session
    finally:
        await engine.dispose()


def run_async(coro):
    return asyncio.run(coro)
