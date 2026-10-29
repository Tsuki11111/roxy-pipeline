from __future__ import annotations

import json
from pathlib import Path

from app.core.config import get_settings
from app.storage.output import export_episode_video


def test_export_episode_video_to_timestamped_output(tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "output_root", str(tmp_path / "output"))
    monkeypatch.setattr(settings, "minio_upload_enabled", False)
    monkeypatch.setattr("app.storage.output.PROJECT_ROOT", tmp_path)

    source = tmp_path / "rendered.mp4"
    source.write_bytes(b"fake mp4")
    exported = export_episode_video(
        source, "8c7ade6b-68eb-43aa-8b15-2e5d4cf3a272", title="测试成片"
    )

    final = Path(exported["path"])
    assert final.is_file()
    assert final.name == "episode.mp4"
    assert final.parent.parent == tmp_path / "output"
    assert len(final.parent.name.split("_")) == 2
    metadata = json.loads((final.parent / "metadata.json").read_text("utf-8"))
    assert metadata["episode_id"].startswith("8c7ade6b")
    assert metadata["title"] == "测试成片"
    assert metadata["minio"] is None


def test_export_can_upload_to_minio(tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "output_root", str(tmp_path / "output"))
    monkeypatch.setattr(settings, "minio_upload_enabled", True)
    monkeypatch.setattr("app.storage.output.PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        "app.storage.output.upload_to_minio",
        lambda path, object_name, **kwargs: {
            "bucket": "roxy-output",
            "object": object_name,
            "uri": f"s3://roxy-output/{object_name}",
        },
    )

    source = tmp_path / "rendered.mp4"
    source.write_bytes(b"fake mp4")
    exported = export_episode_video(source, "episode-12345678", title="上传测试")
    assert exported["meta"]["minio"]["uri"].startswith("s3://roxy-output/")
    metadata = json.loads(
        (Path(exported["path"]).parent / "metadata.json").read_text("utf-8")
    )
    assert metadata["minio"]["bucket"] == "roxy-output"

