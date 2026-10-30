from __future__ import annotations

import base64
import shutil
import uuid
from pathlib import Path

from app.core.config import get_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _asset_root(name: str) -> Path:
    return PROJECT_ROOT / "tmp" / f"{name}_{uuid.uuid4().hex}"


class FakePromptLLM:
    async def chat_json(self, system, user, *, temperature=0.6, max_tokens=600):
        return {"prompt": "a glowing blue prism, transparent background, flat illustration"}


async def test_upload_asset(client, tmp_path, monkeypatch):
    settings = get_settings()
    asset_root = _asset_root("upload_assets")
    monkeypatch.setattr(settings, "asset_root", str(asset_root))
    monkeypatch.setattr(settings, "asset_agent_tmp_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "minio_upload_enabled", False)
    data = (PROJECT_ROOT / "character_packs/placeholder/background.png").read_bytes()
    try:
        response = await client.post(
            "/api/v1/assets/upload",
            json={
                "filename": "custom-prop.png",
                "data_base64": base64.b64encode(data).decode("ascii"),
                "asset_type": "prop",
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "APPROVED"
        assert body["type"] == "prop"
        assert (PROJECT_ROOT / body["path"]).is_file()
    finally:
        shutil.rmtree(asset_root, ignore_errors=True)


async def test_image_prompt_uses_llm(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.assets.build_llm", lambda: FakePromptLLM()
    )
    response = await client.post(
        "/api/v1/assets/image-prompt",
        json={"description": "蓝色发光三棱镜"},
    )
    assert response.status_code == 200, response.text
    assert "prism" in response.json()["prompt"]


async def test_seedream_mock_generates_candidate(client, tmp_path, monkeypatch):
    settings = get_settings()
    asset_root = _asset_root("seedream_assets")
    monkeypatch.setattr(settings, "asset_root", str(asset_root))
    monkeypatch.setattr(settings, "asset_agent_tmp_dir", str(tmp_path / "seedream"))
    monkeypatch.setattr(settings, "minio_upload_enabled", False)
    monkeypatch.setattr(settings, "image_provider", "mock")
    try:
        response = await client.post(
            "/api/v1/assets/seedream",
            json={"prompt": "test prism", "size": "64x64", "count": 1},
        )
        assert response.status_code == 200, response.text
        assets = response.json()["assets"]
        assert len(assets) == 1
        assert assets[0]["status"] == "CANDIDATE"
        assert (PROJECT_ROOT / assets[0]["path"]).is_file()
    finally:
        shutil.rmtree(asset_root, ignore_errors=True)


async def test_asset_file_route_serves_project_image(client):
    response = await client.get(
        "/api/v1/assets/file",
        params={"path": "character_packs/placeholder/background.png"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")


async def test_asset_file_route_rejects_escape(client):
    response = await client.get(
        "/api/v1/assets/file", params={"path": "../secret.png"}
    )
    assert response.status_code == 404
