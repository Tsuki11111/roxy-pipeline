from __future__ import annotations


async def test_human_gate_transitions(client, episode):
    _, ep = episode
    episode_id = ep["id"]

    response = await client.post(f"/api/v1/episodes/{episode_id}/actions/confirm-script")
    assert response.status_code == 409

    response = await client.post(f"/api/v1/episodes/{episode_id}/actions/confirm-topic")
    assert response.status_code == 202, response.text
    accepted = response.json()
    assert accepted["status"] == "SCRIPTING"
    assert accepted["node_key"] == "script.generate"

    response = await client.post(f"/api/v1/episodes/{episode_id}/actions/confirm-script")
    assert response.status_code == 409

    response = await client.post(f"/api/v1/episodes/{episode_id}/actions/cancel")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "CANCELLED"

    response = await client.post(f"/api/v1/episodes/{episode_id}/actions/confirm-topic")
    assert response.status_code == 409
