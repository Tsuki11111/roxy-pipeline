from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.models  # noqa: F401 - register SQLAlchemy models
from app.api.routes import episodes, health, series
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # SQLite is the zero-dependency local mode; Postgres uses Alembic.
    if settings.database_url.startswith("sqlite"):
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(health.router)
app.include_router(series.router)
app.include_router(episodes.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"name": settings.app_name, "docs": "/docs"}
