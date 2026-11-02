"""资产文件哈希、图片信息与复制。"""

from __future__ import annotations

import hashlib
import mimetypes
import shutil
from pathlib import Path

from PIL import Image

from app.storage.paths import relative_project_path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_info(path: Path) -> tuple[int, int, str]:
    with Image.open(path) as image:
        width, height = image.size
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return width, height, mime


def store_asset_file(
    source_path: Path,
    *,
    target_root: Path,
    asset_type: str,
    checksum: str,
) -> str:
    target_dir = target_root.resolve() / asset_type
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{checksum[:16]}{source_path.suffix.lower()}"
    if not target.exists():
        shutil.copy2(source_path, target)
    return relative_project_path(target)