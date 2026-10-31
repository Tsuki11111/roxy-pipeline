from __future__ import annotations

import os

os.environ.setdefault("MINIO_UPLOAD_ENABLED", "false")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - register models on Base.metadata
from app.api.main import app
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_session


@pytest.fixture(autouse=True)
def _allow_playwright_in_tests(monkeypatch):
    monkeypatch.setattr(get_settings(), "remotion_only", False)


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    yield engine, session_factory
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db):
    _, session_factory = db

    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def session(db):
    _, session_factory = db
    async with session_factory() as db_session:
        yield db_session


@pytest_asyncio.fixture
async def episode(client):
    series_response = await client.post(
        "/api/v1/series",
        json={
            "name": "M1.2 测试系列",
            "section_labels": ["问题", "解决", "结尾"],
            "character_pack_id": "placeholder",
            "watermark": "test",
        },
    )
    assert series_response.status_code == 201, series_response.text
    series = series_response.json()

    episode_response = await client.post(
        "/api/v1/episodes",
        json={
            "series_id": series["id"],
            "title": "M1.2 测试期",
            "topic": "渲染队列",
            "target_duration_s": 60,
        },
    )
    assert episode_response.status_code == 201, episode_response.text
    return series, episode_response.json()
