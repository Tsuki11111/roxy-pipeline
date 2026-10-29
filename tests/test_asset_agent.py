from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.agents.asset.service import generate_assets_from_text
from app.core.config import get_settings
from app.models.core import Asset, AssetStatus, AssetType


class FakeLLM:
    def __init__(self, reuse_key: str = "prop:prism") -> None:
        self.reuse_key = reuse_key

    async def chat_json(self, system, user, *, temperature=0.7, max_tokens=2000):
        return {
            "assets": [
                {
                    "type": "prop",
                    "name": "三棱镜",
                    "reuse_key": self.reuse_key,
                    "prompt": "a clean glass prism on white background, no text",
                    "size": "1024x1024",
                    "reason": "解释光的色散",
                }
            ]
        }


class FakeImageProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, prompt: str, out_path: Path, size: str) -> Path:
        self.calls += 1
        out_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (64, 64), (200, 190, 170)).save(out_path)
        return out_path


def _settings(tmp_path: Path, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "asset_root", str(tmp_path / "assets"))
    monkeypatch.setattr(settings, "asset_agent_tmp_dir", str(tmp_path / "agent_tmp"))
    monkeypatch.setattr("app.assets.store.PROJECT_ROOT", tmp_path)


async def test_asset_agent_reuses_approved_asset(
    session, tmp_path, monkeypatch
):
    _settings(tmp_path, monkeypatch)
    image = tmp_path / "existing.png"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(image)
    asset = Asset(
        type=AssetType.PROP,
        name="三棱镜",
        reuse_key="prop:prism",
        path=str(image),
        checksum="0" * 64,
        status=AssetStatus.APPROVED,
        tags=[],
        meta={},
    )
    session.add(asset)
    await session.commit()

    provider = FakeImageProvider()
    result = await generate_assets_from_text(
        session,
        "解释光通过三棱镜后的色散",
        check=False,
        llm=FakeLLM("prop:prism"),
        image_provider=provider,
    )
    assert provider.calls == 0
    assert result["items"][0]["status"] == "reused"
    assert result["items"][0]["asset"].id == asset.id


async def test_asset_agent_generates_candidate(
    session, tmp_path, monkeypatch
):
    _settings(tmp_path, monkeypatch)
    provider = FakeImageProvider()
    result = await generate_assets_from_text(
        session,
        "解释光通过三棱镜后的色散",
        check=False,
        llm=FakeLLM("prop:prism-new"),
        image_provider=provider,
    )
    assert provider.calls == 1
    item = result["items"][0]
    assert item["status"] == "generated"
    assert item["asset"].status == AssetStatus.CANDIDATE
    assert item["asset"].source == "asset_agent"
    assert Path(item["asset"].path).is_file() or (tmp_path / item["asset"].path).is_file()


async def test_asset_agent_api(client, session, tmp_path, monkeypatch):
    _settings(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "app.agents.asset.service.build_llm", lambda: FakeLLM("prop:api-prism")
    )
    monkeypatch.setattr(
        "app.agents.asset.service.build_image_provider",
        lambda: FakeImageProvider(),
    )

    response = await client.post(
        "/api/v1/assets/generate",
        json={
            "text": "解释光的色散",
            "asset_type": "prop",
            "count": 1,
            "check": False,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["items"][0]["status"] == "generated"
    assert body["items"][0]["asset"]["reuse_key"] == "prop:api-prism"
