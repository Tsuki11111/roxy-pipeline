from __future__ import annotations

import atexit
import json
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TTSError(RuntimeError):
    pass


@dataclass(frozen=True)
class TTSResult:
    audio_path: Path
    duration_ms: int
    sample_rate: int


class TTSProvider(Protocol):
    def synthesize(
        self,
        text: str,
        out_path: Path,
        *,
        speed: float = 1.0,
        emotion: str | None = None,
    ) -> TTSResult:
        ...


def _resolve(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def request_tts_shutdown(timeout_s: float = 10.0) -> bool:
    """Stop the resident TTS server to free memory for the aligner."""
    settings = get_settings()
    url = f"{settings.tts_indextts_url.rstrip('/')}/shutdown"
    request = urllib.request.Request(
        url,
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            if response.status != 200:
                return False
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        return False

    deadline = time.monotonic() + timeout_s
    health_url = f"{settings.tts_indextts_url.rstrip('/')}/health"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=1):
                pass
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            return True
        time.sleep(0.2)
    return False


class IndexTTS2Provider:
    """IndexTTS2 zero-shot TTS served by a long-lived local process.

    The model is loaded once and kept in VRAM; each sentence is one HTTP call.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.python = _resolve(settings.tts_indextts_python)
        self.repo = _resolve(settings.tts_indextts_repo)
        self.model_dir = _resolve(settings.tts_indextts_model_dir)
        self.server_script = _resolve(settings.tts_indextts_server)
        self.ref_audio = _resolve(settings.tts_indextts_ref_audio)
        self.base_url = settings.tts_indextts_url.rstrip("/")
        self.fp16 = settings.tts_indextts_use_fp16
        self.semantic_on_cpu = settings.tts_indextts_semantic_on_cpu
        self.load_timeout_s = settings.tts_indextts_load_timeout_s
        self.timeout_s = settings.tts_indextts_timeout_s
        self.log_path = _resolve(settings.tts_indextts_log)

        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None

    def _check_files(self) -> None:
        for path in (
            self.python,
            self.repo,
            self.model_dir,
            self.server_script,
            self.ref_audio,
        ):
            if not path.exists():
                raise TTSError(f"TTS dependency not found: {path}")

    def _healthy(self) -> bool:
        try:
            with urllib.request.urlopen(
                f"{self.base_url}/health", timeout=2
            ) as response:
                return response.status == 200
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            return False

    def _log_tail(self, limit: int = 2000) -> str:
        try:
            return self.log_path.read_text(encoding="utf-8", errors="replace")[-limit:]
        except OSError:
            return ""

    def _start_server(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = self.log_path.open("a", encoding="utf-8")
        cmd = [
            str(self.python),
            str(self.server_script),
            "--repo",
            str(self.repo),
            "--model-dir",
            str(self.model_dir),
            "--port",
            self.base_url.rsplit(":", 1)[-1],
        ]
        if self.fp16:
            cmd.append("--fp16")
        if self.semantic_on_cpu:
            cmd.append("--semantic-on-cpu")
        env = __import__("os").environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
        self._proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def _wait_ready(self) -> None:
        deadline = time.monotonic() + self.load_timeout_s
        while time.monotonic() < deadline:
            if self._healthy():
                return
            if self._proc is not None and self._proc.poll() is not None:
                raise TTSError(
                    f"IndexTTS2 server exited ({self._proc.returncode}): "
                    f"{self._log_tail()}"
                )
            time.sleep(1)
        raise TTSError(
            f"IndexTTS2 server not ready after {self.load_timeout_s}s: "
            f"{self._log_tail()}"
        )

    def _ensure_server(self) -> None:
        if self._healthy():
            return
        self._start_server()
        self._wait_ready()

    def synthesize(
        self,
        text: str,
        out_path: Path,
        *,
        speed: float = 1.0,
        emotion: str | None = None,
    ) -> TTSResult:
        self._check_files()
        if abs(speed - 1.0) > 0.01:
            raise TTSError("IndexTTS2 provider does not support speed adjustment yet")
        if emotion is not None:
            raise TTSError("IndexTTS2 provider does not support emotion yet")
        text = " ".join(text.split())
        if not text:
            raise TTSError("empty text")
        out_path = out_path.resolve()

        with self._lock:
            self._ensure_server()
            payload = json.dumps(
                {
                    "text": text,
                    "out_path": str(out_path),
                    "ref_audio": str(self.ref_audio),
                },
                ensure_ascii=False,
            ).encode("utf-8")
            request = urllib.request.Request(
                f"{self.base_url}/synthesize",
                data=payload,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(
                    request, timeout=self.timeout_s
                ) as response:
                    body = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[-2000:]
                raise TTSError(f"IndexTTS2 synthesis failed: {detail}") from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                raise TTSError(f"IndexTTS2 request failed: {exc}") from exc

        audio_path = Path(body["audio_path"])
        if not audio_path.is_file():
            raise TTSError(f"IndexTTS2 produced no audio: {audio_path}")
        return TTSResult(
            audio_path=audio_path,
            duration_ms=int(body["duration_ms"]),
            sample_rate=int(body["sample_rate"]),
        )

    def close(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is None or proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def build_tts_provider() -> TTSProvider:
    settings = get_settings()
    if settings.tts_provider == "indextts2":
        provider = IndexTTS2Provider()
        atexit.register(provider.close)
        return provider
    raise TTSError(f"unsupported TTS_PROVIDER: {settings.tts_provider}")
