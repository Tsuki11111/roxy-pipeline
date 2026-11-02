from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.qc.tasks import _prune_qc_frames
from app.storage.output import prune_episode_outputs
from app.workflow import cleanup


def _make_output(root, name: str) -> None:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "episode.mp4").write_bytes(b"video")


def test_prune_episode_outputs_keeps_current_and_latest(tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "output_root", str(tmp_path))
    monkeypatch.setattr(settings, "output_keep_versions", 2)
    old = "20260101-000000_abcdef12"
    middle = "20260102-000000_abcdef12"
    latest = "20260103-000000_abcdef12"
    other = "20260104-000000_ffffffff"
    for name in (old, middle, latest, other):
        _make_output(tmp_path, name)

    deleted = prune_episode_outputs("abcdef12-0000-0000-0000-000000000000", tmp_path / latest / "episode.mp4")

    assert deleted == [old]
    assert (tmp_path / middle).is_dir()
    assert (tmp_path / latest).is_dir()
    assert (tmp_path / other).is_dir()


def test_prune_qc_frames_keeps_only_referenced_evidence(tmp_path):
    frames = tmp_path / "tmp" / "qc" / "episode-1" / "frames"
    frames.mkdir(parents=True)
    keep = frames / "shot_0001_1.jpg"
    drop = frames / "shot_0001_2.jpg"
    keep.write_bytes(b"keep")
    drop.write_bytes(b"drop")

    removed = _prune_qc_frames(
        frames.parent,
        [{"evidence_path": str(keep)}],
    )

    assert removed == 1
    assert keep.is_file()
    assert not drop.exists()


async def test_cleanup_temp_dirs_removes_old_orphans(
    session, tmp_path, monkeypatch
):
    settings = get_settings()
    remotion = tmp_path / "remotion"
    renders = tmp_path / "renders"
    qc = tmp_path / "tmp" / "qc"
    for root, name in (
        (remotion, "old-episode"),
        (renders, "old-episode"),
        (qc, "old-episode"),
    ):
        root.mkdir(parents=True)
        target = root / name
        target.mkdir()
        (target / "artifact.bin").write_bytes(b"old")
        old = (datetime.now(timezone.utc) - timedelta(days=10)).timestamp()
        os.utime(target, (old, old))
    young = renders / "young-episode"
    young.mkdir()

    monkeypatch.setattr(settings, "remotion_work_root", str(remotion))
    monkeypatch.setattr(settings, "render_dir", str(renders))
    monkeypatch.setattr(settings, "tmp_remotion_retention_days", 7)
    monkeypatch.setattr(settings, "tmp_renders_retention_days", 7)
    monkeypatch.setattr(settings, "tmp_qc_retention_days", 3)
    monkeypatch.setattr(cleanup, "PROJECT_ROOT", tmp_path)

    result = await cleanup.cleanup_temp_dirs(session)

    assert "remotion:old-episode" in result["deleted"]
    assert "renders:old-episode" in result["deleted"]
    assert "qc:old-episode" in result["deleted"]
    assert young.is_dir()