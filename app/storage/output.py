from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import get_settings

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def upload_to_minio(
    local_path: Path,
    object_name: str,
    *,
    bucket: str | None = None,
    content_type: str = "application/octet-stream",
) -> dict:
    settings = get_settings()
    if not settings.minio_upload_enabled:
        return {"skipped": True, "reason": "MINIO_UPLOAD_ENABLED=false"}

    from minio import Minio
    from urllib3 import PoolManager

    parsed = urlparse(settings.minio_internal_endpoint)
    endpoint = parsed.netloc or settings.minio_internal_endpoint
    secure = parsed.scheme == "https"
    bucket = bucket or settings.minio_bucket_output
    client = Minio(
        endpoint,
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password,
        secure=secure,
        http_client=PoolManager(
            timeout=settings.minio_timeout_s, retries=False
        ),
    )
    try:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
        client.fput_object(
            bucket,
            object_name,
            str(local_path),
            content_type=content_type,
        )
    except Exception:
        raise
    return {
        "bucket": bucket,
        "object": object_name,
        "uri": f"s3://{bucket}/{object_name}",
    }


def export_episode_video(
    source: Path,
    episode_id: str,
    *,
    title: str = "",
) -> dict:
    settings = get_settings()
    root = _resolve(settings.output_root)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = root / f"{stamp}_{episode_id[:8]}"
    if out_dir.exists():
        out_dir = root / f"{stamp}_{episode_id[:8]}-{datetime.now().microsecond:06d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    final = out_dir / "episode.mp4"
    shutil.copy2(source, final)

    meta = {
        "episode_id": episode_id,
        "title": title,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "local_path": str(final),
        "relative_path": (
            final.relative_to(PROJECT_ROOT).as_posix()
            if final.is_relative_to(PROJECT_ROOT)
            else str(final)
        ),
        "minio": None,
    }
    if settings.minio_upload_enabled:
        try:
            meta["minio"] = upload_to_minio(
                final,
                f"episodes/{out_dir.name}/episode.mp4",
                content_type="video/mp4",
            )
        except Exception as exc:
            meta["minio_error"] = str(exc)[:1000]
            logger.warning("MinIO upload failed for %s: %s", final, exc)
            if settings.minio_required:
                raise

    (out_dir / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"path": str(final), "meta": meta}
