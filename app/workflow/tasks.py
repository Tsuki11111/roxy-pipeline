from __future__ import annotations

from celery.utils.log import get_task_logger

from app.workflow.celery_app import celery_app
from app.workflow.db import run_async, task_session
from app.workflow.outbox import dispatch_pending

logger = get_task_logger(__name__)


@celery_app.task(name="workflow.dispatch_outbox")
def dispatch_outbox_task(limit: int = 50):
    async def _dispatch():
        async with task_session() as session:
            events = await dispatch_pending(session, limit=limit)
            return [event.id for event in events]

    dispatched = run_async(_dispatch())
    if dispatched:
        logger.info("dispatched %d outbox events", len(dispatched))
    return {"dispatched": dispatched}
