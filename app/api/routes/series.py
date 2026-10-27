from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.core import Series
from app.schemas.core import SeriesCreate, SeriesRead

router = APIRouter(prefix="/api/v1/series", tags=["series"])


@router.post("", response_model=SeriesRead, status_code=status.HTTP_201_CREATED)
async def create_series(
    payload: SeriesCreate,
    session: AsyncSession = Depends(get_session),
) -> Series:
    existing = await session.scalar(select(Series).where(Series.name == payload.name))
    if existing is not None:
        raise HTTPException(status_code=409, detail="series name already exists")
    series = Series(**payload.model_dump())
    session.add(series)
    await session.commit()
    await session.refresh(series)
    return series


@router.get("", response_model=list[SeriesRead])
async def list_series(session: AsyncSession = Depends(get_session)) -> list[Series]:
    result = await session.scalars(select(Series).order_by(Series.created_at.desc()))
    return list(result)


@router.get("/{series_id}", response_model=SeriesRead)
async def get_series(
    series_id: str,
    session: AsyncSession = Depends(get_session),
) -> Series:
    series = await session.get(Series, series_id)
    if series is None:
        raise HTTPException(status_code=404, detail="series not found")
    return series
