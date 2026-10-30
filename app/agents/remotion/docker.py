from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class RemotionDockerError(RuntimeError):
    pass


def workdir_for(episode_id: str) -> Path:
    settings = get_settings()
    root = Path(settings.remotion_work_root).expanduser()
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    return root.resolve() / episode_id


def _docker() -> str:
    return get_settings().remotion_docker_bin


def image_available() -> bool:
    settings = get_settings()
    try:
        result = subprocess.run(
            [_docker(), "image", "inspect", settings.remotion_image],
            capture_output=True,
            text=True,
            timeout=20,
            env={**os.environ, "MSYS_NO_PATHCONV": "1"},
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def image_digest() -> str | None:
    settings = get_settings()
    try:
        result = subprocess.run(
            [
                _docker(),
                "image",
                "inspect",
                settings.remotion_image,
                "--format",
                "{{.Id}}",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            env={**os.environ, "MSYS_NO_PATHCONV": "1"},
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _mount(source: Path, target: str, *, read_only: bool = False) -> list[str]:
    mode = "ro" if read_only else "rw"
    return ["-v", f"{source.resolve()}:{target}:{mode}"]


def _run(
    workdir: Path,
    script: str,
    args: list[str],
    *,
    timeout: float,
) -> str:
    settings = get_settings()
    out_dir = workdir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    command = [
        _docker(),
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp",
        "--tmpfs",
        "/app/node_modules/.cache",
        "--user",
        "10001",
        "--cpus",
        "2",
        "-m",
        "3g",
        "--pids-limit",
        "256",
        "-e",
        "TMPDIR=/tmp",
        *_mount(workdir / "src", "/app/src", read_only=True),
        *_mount(workdir / "public", "/app/public", read_only=True),
        *_mount(out_dir, "/app/out"),
        settings.remotion_image,
        "node",
        f"/app/scripts/{script}",
        *args,
    ]
    env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise RemotionDockerError(
            f"Remotion sandbox timed out after {timeout:.0f}s"
        ) from exc
    except OSError as exc:
        raise RemotionDockerError(f"cannot run docker: {exc}") from exc
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        raise RemotionDockerError(output.strip()[-5000:] or "Remotion failed")
    return output


def validate_workdir(workdir: Path) -> str:
    if not image_available():
        raise RemotionDockerError(
            "Remotion image not available; build infra/remotion first"
        )
    return _run(
        workdir,
        "validate.mjs",
        [],
        timeout=get_settings().remotion_validate_timeout_s,
    )


def render_shot(
    workdir: Path,
    composition_id: str,
    output_name: str = "shot.mp4",
) -> Path:
    if not image_available():
        raise RemotionDockerError(
            "Remotion image not available; build infra/remotion first"
        )
    _run(
        workdir,
        "render-shot.mjs",
        ["--comp", composition_id, "--out", f"/app/out/{output_name}"],
        timeout=get_settings().remotion_render_timeout_s,
    )
    output = workdir / "out" / output_name
    if not output.is_file() or output.stat().st_size == 0:
        raise RemotionDockerError(f"Remotion produced no video: {output}")
    return output
