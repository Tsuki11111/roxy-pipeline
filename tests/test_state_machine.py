from __future__ import annotations


async def test_human_gate_transitions(client, episode):
    _, ep = episode
    episode_id = ep["id"]

    response = await client.post(f"/api/v1/episodes/{episode_id}/actions/confirm-script")
    assert response.status_code == 409

    response = await client.post(f"/api/v1/episodes/{episode_id}/actions/cancel")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "CANCELLED"

    response = await client.post(f"/api/v1/episodes/{episode_id}/actions/confirm-script")
    assert response.status_code == 409


async def test_delete_episode_only_when_not_running(client, episode, session):
    _, ep = episode
    episode_id = ep["id"]
    response = await client.delete(f"/api/v1/episodes/{episode_id}")
    assert response.status_code == 204, response.text
    response = await client.get(f"/api/v1/episodes/{episode_id}")
    assert response.status_code == 404
