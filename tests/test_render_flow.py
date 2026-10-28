from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.models.core import NodeRun, OutboxEvent, OutboxStatus
from app.workflow.outbox import dispatch_pending

SPEC_PATH = Path(__file__).resolve().parents[1] / "specs" / "demo_placeholder.json"


def load_spec() -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


async def test_put_spec_and_queue_render(client, episode, session):
    _, ep = episode
    episode_id = ep["id"]

    response = await client.post(f"/api/v1/episodes/{episode_id}/actions/render")
    assert response.status_code == 400

    response = await client.put(
        f"/api/v1/episodes/{episode_id}/render-spec", json=load_spec()
    )
    assert response.status_code == 200, response.text
    assert response.json()["render_spec"]["title"]

    response = await client.post(f"/api/v1/episodes/{episode_id}/actions/render")
    assert response.status_code == 202, response.text
    accepted = response.json()
    assert accepted["status"] == "RENDERING"
    assert accepted["node_key"] == "render.episode"

    response = await client.post(f"/api/v1/episodes/{episode_id}/actions/render")
    assert response.status_code == 409

    response = await client.put(
        f"/api/v1/episodes/{episode_id}/render-spec", json=load_spec()
    )
    assert response.status_code == 409

    event = await session.scalar(select(OutboxEvent))
    assert event is not None
    assert event.event_type == "render.episode"
    assert event.status == OutboxStatus.PENDING
    assert event.payload["node_run_id"] == accepted["operation_id"]

    node = await session.get(NodeRun, accepted["operation_id"])
    assert node is not None
    assert node.status == "PENDING"

    sent = []
    dispatched = await dispatch_pending(session, sender=sent.append)
    assert len(dispatched) == 1
    assert sent[0].id == event.id

    await session.refresh(event)
    assert event.status == OutboxStatus.DISPATCHED
    assert event.attempts == 1


async def test_render_spec_rejects_missing_assets(client, episode):
    _, ep = episode
    spec = load_spec()
    spec["background"] = "tmp/does-not-exist.png"

    response = await client.put(
        f"/api/v1/episodes/{ep['id']}/render-spec", json=spec
    )
    assert response.status_code == 422
