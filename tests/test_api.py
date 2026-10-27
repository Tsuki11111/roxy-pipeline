from __future__ import annotations


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


async def test_create_series_and_episode(client):
    series_response = await client.post(
        "/api/v1/series",
        json={
            "name": "AI 科普测试系列",
            "section_labels": ["问题", "概念", "解决"],
            "character_pack_id": "roxy",
            "watermark": "test",
        },
    )
    assert series_response.status_code == 201, series_response.text
    series = series_response.json()
    assert series["name"] == "AI 科普测试系列"

    episode_response = await client.post(
        "/api/v1/episodes",
        json={
            "series_id": series["id"],
            "title": "第一集",
            "topic": "测试",
            "target_duration_s": 60,
        },
    )
    assert episode_response.status_code == 201, episode_response.text
    episode = episode_response.json()
    assert episode["status"] == "DRAFT"
    assert episode["series_id"] == series["id"]

    get_response = await client.get(f"/api/v1/episodes/{episode['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "第一集"

    list_response = await client.get("/api/v1/episodes", params={"status": "DRAFT"})
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


async def test_episode_requires_existing_series(client):
    response = await client.post(
        "/api/v1/episodes",
        json={"series_id": "missing", "title": "x"},
    )
    assert response.status_code == 404
