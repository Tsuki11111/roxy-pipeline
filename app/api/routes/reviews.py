from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.core import Review
from app.schemas.core import ReviewRead

router = APIRouter(prefix="/api/v1/reviews", tags=["qc"])


@router.post("/{review_id}/resolve", response_model=ReviewRead)
async def resolve_review(
    review_id: str,
    resolved_by: str = Query(default="operator"),
    session: AsyncSession = Depends(get_session),
) -> Review:
    review = await session.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="review not found")
    review.resolved_by = resolved_by
    review.resolved_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(review)
    return review
