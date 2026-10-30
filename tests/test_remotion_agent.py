from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.agents.remotion.service import (
    generate_remotion_code,
    start_remotion_codegen,
)
from app.core.config import get_settings
from app.models.core import (
    Episode,
    EpisodeStatus,
    NodeRun,
    OutboxEvent,
    RemotionShot,
    ScriptLine,
    Shot,
)

CODE = """import {AbsoluteFill, useCurrentFrame} from 'remotion';

export const Shot_0001 = () => {
  const frame = useCurrentFrame();
  return <AbsoluteFill style={{backgroundColor: '#1e1e2e', opacity: Math.min(1, frame / 25)}} />;
};
"""


class FakeRemotionLLM:
    async def chat_json(self, system, user, *, temperature=0.7, max_tokens=2000):
        return {
            "schema_version": "1",
            "component_name": "Shot_0001",
            "code": CODE,
            "summary": "test shot",
        }


async def seed_ready_episode(session, episode_id: str) -> None:
    session.add(
        ScriptLine(
            episode_id=episode_id,
            seq=1,
            speaker="narrator",
            section="问题",
            text="这是用于 Remotion 测试的一句台词",
            char_count=15,
        )
    )
    await session.flush()
    line = await session.scalar(
        select(ScriptLine).where(ScriptLine.episode_id == episode_id)
    )
    session.add(
        Shot(
            episode_id=episode_id,
            script_line_id=line.id,
            seq=1,
            duration_ms=2000,
            card_type="pure_text",
            card_payload={"text": "测试卡片"},
            character_image="character_packs/placeholder/character.png",
            character_position="left",
            bg="paper",
        )
    )
    episode = await session.get(Episode, episode_id)
    episode.status = EpisodeStatus.READY
    await session.commit()


async def test_start_remotion_codegen_queues_task(client, episode, session):
    _, ep = episode
    await seed_ready_episode(session, ep["id"])

    response = await client.post(
        f"/api/v1/episodes/{ep['id']}/actions/generate-remotion",
        json={},
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["node_key"] == "remotion.codegen"
    assert body["status"] == "READY"

    node = await session.get(NodeRun, body["operation_id"])
    assert node is not None
    assert node.status == "PENDING"
    event = await session.scalar(
        select(OutboxEvent).where(OutboxEvent.event_type == "remotion.generate")
    )
    assert event is not None
    assert event.payload["episode_id"] == ep["id"]


async def test_generate_remotion_code_persists_component_and_meta(
    episode, session, monkeypatch
):
    _, ep = episode
    await seed_ready_episode(session, ep["id"])
    settings = get_settings()
    monkeypatch.setattr(settings, "remotion_codegen_concurrency", 1)
    monkeypatch.setattr(
        "app.agents.remotion.service.build_llm", lambda: FakeRemotionLLM()
    )
    monkeypatch.setattr(
        "app.agents.remotion.docker.validate_workdir", lambda workdir: ""
    )
    monkeypatch.setattr(
        "app.agents.remotion.docker.image_digest", lambda: "sha256:test"
    )

    episode_row = await session.get(Episode, ep["id"])
    _, node = await start_remotion_codegen(session, ep["id"])
    await session.commit()

    result = await generate_remotion_code(session, ep["id"], node.id)
    await session.commit()

    assert result["meta"]["enabled"] is True
    row = await session.scalar(
        select(RemotionShot).where(RemotionShot.episode_id == ep["id"])
    )
    assert row is not None
    assert row.status == "READY"
    assert row.composition_id == "Shot-0001"

    meta = episode_row.remotion_meta
    assert meta is not None
    assert meta["status"] == "ready"
    workdir = Path(meta["work_dir"])
    if not workdir.is_absolute():
        workdir = Path.cwd() / workdir
    assert (workdir / row.code_path).is_file()
    assert (workdir / "src" / "Root.tsx").is_file()
    root = (workdir / "src" / "Root.tsx").read_text(encoding="utf-8")
    assert "Shot_0001" in root
    assert "durationInFrames={50}" in root


async def test_render_spec_uses_remotion_when_meta_ready(
    episode, session, monkeypatch
):
    from app.agents.storyboard.render_spec import build_episode_render_spec

    _, ep = episode
    await seed_ready_episode(session, ep["id"])
    episode_row = await session.get(Episode, ep["id"])
    shot = await session.scalar(
        select(Shot).where(Shot.episode_id == ep["id"])
    )
    episode_row.remotion_meta = {
        "enabled": True,
        "work_dir": "tmp/remotion/test",
        "version": "4.0.539",
        "image_digest": "sha256:test",
        "shots": {
            shot.id: {
                "status": "READY",
                "composition_id": "Shot_0001",
                "code_hash": "abc",
            }
        },
    }
    await session.commit()

    spec = await build_episode_render_spec(session, episode_row)
    assert spec.renderer == "remotion"
    assert spec.remotion is not None
    assert spec.remotion.shots[shot.id].code_hash == "abc"

    from app.render.tasks import shot_render_hash
    from app.render.timeline import build_timeline

    item = build_timeline(spec).shots[0]
    base = shot_render_hash(spec, item)
    spec.remotion.shots[shot.id].code_hash = "def"
    assert shot_render_hash(spec, item) != base
    spec.renderer = "playwright"
    spec.remotion = None
    assert shot_render_hash(spec, item) != base
