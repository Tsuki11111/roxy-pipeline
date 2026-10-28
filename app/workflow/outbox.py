from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import OutboxEvent, OutboxStatus


def queue_for(event_type: str) -> str:
    if event_type.startswith("render."):
        return "render"
    if event_type.startswith("script."):
        return "agent"
    return "workflow"


def default_sender(event: OutboxEvent) -> None:
    from app.workflow.celery_app import celery_app

    celery_app.send_task(
        event.event_type,
        kwargs=event.payload,
        queue=queue_for(event.event_type),
        task_id=event.id,
    )


async def enqueue_outbox(
    session: AsyncSession,
    event_type: str,
    payload: dict,
    *,
    episode_id: str | None = None,
    available_at: datetime | None = None,
) -> OutboxEvent:
    event = OutboxEvent(
        episode_id=episode_id,
        event_type=event_type,
        payload=payload,
        available_at=available_at or datetime.now(timezone.utc),
    )
    session.add(event)
    await session.flush()
    return event


async def dispatch_pending(
    session: AsyncSession,
    *,
    sender: Callable[[OutboxEvent], None] | None = None,
    limit: int = 50,
    max_attempts: int = 5,
    now: datetime | None = None,
) -> list[OutboxEvent]:
    """Publish pending outbox events; retries use exponential backoff."""
    sender = sender or default_sender
    now = now or datetime.now(timezone.utc)
    stmt = (
        select(OutboxEvent)
        .where(
            OutboxEvent.status == OutboxStatus.PENDING,
            OutboxEvent.available_at <= now,
        )
        .order_by(OutboxEvent.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    events = list(await session.scalars(stmt))
    dispatched: list[OutboxEvent] = []
    for event in events:
        event.attempts += 1
        try:
            sender(event)
        except Exception as exc:  # broker/network errors; keep the event for retry
            event.error = str(exc)[:2000]
            if event.attempts >= max_attempts:
                event.status = OutboxStatus.FAILED
            else:
                event.available_at = now + timedelta(
                    seconds=min(300, 2**event.attempts)
                )
        else:
            event.status = OutboxStatus.DISPATCHED
            event.dispatched_at = now
            event.error = None
            dispatched.append(event)
        await session.commit()
    return dispatched
