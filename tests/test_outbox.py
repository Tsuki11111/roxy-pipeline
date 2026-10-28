from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.core import OutboxEvent, OutboxStatus
from app.workflow.celery_app import celery_app
from app.workflow.outbox import default_sender, dispatch_pending, queue_for


async def test_outbox_retry_and_success(session):
    event = OutboxEvent(event_type="render.shot", payload={"seq": 1})
    session.add(event)
    await session.commit()

    def fail(_):
        raise RuntimeError("broker down")

    now = datetime.now(timezone.utc)
    dispatched = await dispatch_pending(session, sender=fail, now=now)
    assert dispatched == []
    await session.refresh(event)
    assert event.status == OutboxStatus.PENDING
    assert event.attempts == 1
    available_at = event.available_at
    if available_at.tzinfo is None:
        available_at = available_at.replace(tzinfo=timezone.utc)
    assert available_at > now

    sent = []
    dispatched = await dispatch_pending(
        session,
        sender=sent.append,
        now=now + timedelta(seconds=10),
    )
    assert len(dispatched) == 1
    await session.refresh(event)
    assert event.status == OutboxStatus.DISPATCHED
    assert event.attempts == 2
    assert sent[0].id == event.id


async def test_outbox_gives_up_after_max_attempts(session):
    event = OutboxEvent(event_type="render.shot", payload={"seq": 2})
    session.add(event)
    await session.commit()

    def fail(_):
        raise RuntimeError("broker down")

    now = datetime.now(timezone.utc)
    await dispatch_pending(session, sender=fail, max_attempts=1, now=now)
    await session.refresh(event)
    assert event.status == OutboxStatus.FAILED
    assert event.attempts == 1


def test_default_sender_passes_payload_as_kwargs(monkeypatch):
    calls: dict = {}

    def fake_send_task(name, **kwargs):
        calls["name"] = name
        calls.update(kwargs)

    monkeypatch.setattr(celery_app, "send_task", fake_send_task)
    payload = {
        "episode_id": "ep",
        "node_run_id": "node",
        "spec": {},
        "seq": 1,
        "out_dir": "tmp",
    }
    event = OutboxEvent(
        id="evt-1", event_type="render.shot", payload=payload
    )
    default_sender(event)

    assert calls["name"] == "render.shot"
    assert calls["queue"] == "render"
    assert calls["task_id"] == "evt-1"
    assert calls["kwargs"] == payload
    assert queue_for("workflow.dispatch_outbox") == "workflow"

