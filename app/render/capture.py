from __future__ import annotations

import threading
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

from .encode import finish_segment, start_segment
from .timeline import Timeline


@contextmanager
def local_server(root: Path):
    class QuietHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def log_message(self, format, *args):  # noqa: A002
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def render_still(
    payload: dict,
    out: Path,
    t_ms: int,
    width: int,
    height: int,
) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with local_server(Path(__file__).resolve().parents[2]) as base_url:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": width, "height": height},
                device_scale_factor=1,
            )
            page.goto(f"{base_url}/templates/stage/stage.html", wait_until="load")
            page.evaluate("window.initStage", payload)
            page.wait_for_function("window.stageReady === true", timeout=60_000)
            page.evaluate("window.renderAt", t_ms)
            page.screenshot(
                path=str(out),
                type="png",
                clip={"x": 0, "y": 0, "width": width, "height": height},
            )
            browser.close()


def _render_shot_frames(
    page,
    item,
    out_dir: Path,
    ffmpeg: str,
    width: int,
    height: int,
    fps: int,
) -> tuple[Path, Path]:
    seq = item.shot.seq
    shots_dir = out_dir / "shots"
    frames_dir = out_dir / "frames"
    shots_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)

    segment = shots_dir / f"shot_{seq:04d}.mp4"
    first_frame = frames_dir / f"shot_{seq:04d}_first.png"
    proc = start_segment(ffmpeg, segment, fps)
    assert proc.stdin is not None
    for frame in range(item.frame_start, item.frame_end):
        t_ms = frame * 1000 / fps
        page.evaluate("window.renderAt", t_ms)
        png = page.screenshot(
            type="png",
            clip={"x": 0, "y": 0, "width": width, "height": height},
        )
        if frame == item.frame_start:
            first_frame.write_bytes(png)
        try:
            proc.stdin.write(png)
        except BrokenPipeError as exc:
            stderr = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
            raise RuntimeError(f"ffmpeg pipe closed for shot {seq}:\n{stderr}") from exc
    finish_segment(proc)
    return segment, first_frame


def render_shot(
    payload: dict,
    item,
    out_dir: Path,
    ffmpeg: str,
    width: int,
    height: int,
    fps: int,
) -> tuple[Path, Path]:
    """Render one shot in its own browser; used by render-worker tasks."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with local_server(Path(__file__).resolve().parents[2]) as base_url:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": width, "height": height},
                device_scale_factor=1,
            )
            try:
                page.goto(f"{base_url}/templates/stage/stage.html", wait_until="load")
                page.evaluate("window.initStage", payload)
                page.wait_for_function("window.stageReady === true", timeout=60_000)
                return _render_shot_frames(
                    page, item, out_dir, ffmpeg, width, height, fps
                )
            finally:
                browser.close()


def render_episode(
    payload: dict,
    timeline: Timeline,
    out_dir: Path,
    ffmpeg: str,
    width: int,
    height: int,
    fps: int,
    still_ms: int | None = None,
) -> list[Path]:
    shots_dir = out_dir / "shots"
    frames_dir = out_dir / "frames"
    shots_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)

    with local_server(Path(__file__).resolve().parents[2]) as base_url:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": width, "height": height},
                device_scale_factor=1,
            )
            page.goto(f"{base_url}/templates/stage/stage.html", wait_until="load")
            page.evaluate("window.initStage", payload)
            page.wait_for_function("window.stageReady === true", timeout=60_000)

            if still_ms is not None:
                page.evaluate("window.renderAt", still_ms)
                page.screenshot(
                    path=str(out_dir / "preview.png"),
                    type="png",
                    clip={"x": 0, "y": 0, "width": width, "height": height},
                )

            segments: list[Path] = []
            for item in timeline.shots:
                segment, _ = _render_shot_frames(
                    page, item, out_dir, ffmpeg, width, height, fps
                )
                segments.append(segment)
                print(f"rendered shot {item.shot.seq}: {item.frame_count} frames -> {segment.name}")

            browser.close()
    return segments
