from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "dev"
    app_name: str = "Roxy Pipeline"

    # local dev defaults to SQLite so the API can run without Docker
    database_url: str = "sqlite+aiosqlite:///./tmp/roxy.db"

    # Service endpoints are environment-driven. The defaults below are
    # local-only fallbacks; business code must always read them from Settings.
    rabbitmq_url: str = "amqp://roxy:change-me@localhost:5673//"
    redis_url: str = "redis://localhost:6380/0"

    minio_internal_endpoint: str = "http://localhost:9100"
    minio_public_endpoint: str = "http://localhost:9100"
    minio_root_user: str = "roxy"
    minio_root_password: str = "change-me"
    minio_bucket_assets: str = "roxy-assets"
    minio_bucket_artifacts: str = "roxy-artifacts"
    minio_bucket_output: str = "roxy-output"
    output_root: str = "./output"
    minio_upload_enabled: bool = True
    minio_required: bool = False
    minio_timeout_s: float = 10.0

    app_secret_key: str = "dev-only-change-me"
    jwt_secret: str = "dev-only-change-me"

    # LLM (M2 script agent). The key itself only lives in the local .env.
    llm_provider: str = "deepseek"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    llm_timeout_s: float = 120.0

    # Image generation (Seedream). IMAGE_PROVIDER=mock can be used when the
    # Ark image model is not enabled.
    image_provider: str = "ark"
    ark_api_key: str = ""
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    ark_image_model: str = "doubao-seedream-5-0-pro-260628"
    image_size: str = "1080x1920"
    image_candidates: int = 4
    asset_agent_tmp_dir: str = "./tmp/asset_agent"
    asset_agent_auto_check: bool = True
    asset_agent_max_count: int = 3

    script_target_chars_per_minute: int = 327
    script_article_max_chars: int = 30000

    storyboard_max_repairs: int = 2

    # M4 local TTS: IndexTTS2 zero-shot voice cloning. The model runs in an
    # isolated Python 3.11 environment and is kept resident behind a local
    # HTTP service; paths stay local defaults and can be overridden in .env.
    tts_provider: str = "indextts2"
    tts_indextts_python: str = "./data/tools/indextts-venv/Scripts/python.exe"
    tts_indextts_repo: str = "./data/tools/IndexTTS2"
    tts_indextts_model_dir: str = "./data/assets/voice/indextts2/IndexTTS-2"
    tts_indextts_server: str = "./scripts/runtime/indextts_server.py"
    tts_indextts_ref_audio: str = "./data/assets/voice/indextts2/reference.wav"
    tts_indextts_url: str = "http://127.0.0.1:8765"
    tts_indextts_use_fp16: bool = True
    tts_indextts_semantic_on_cpu: bool = True
    tts_unload_after_voice: bool = True
    tts_indextts_load_timeout_s: float = 600.0
    tts_indextts_timeout_s: float = 600.0
    tts_indextts_log: str = "./data/logs/indextts_server.log"

    # M4.1 voice track. Sentence audio is content-addressed under audio_root;
    # gaps are inserted between lines so audio length matches shot durations.
    audio_root: str = "./data/audio"
    voice_pause_ms: int = 180
    voice_auto_align: bool = True
    voice_auto_render: bool = True

    # M4.2 character-level forced alignment (WhisperX's Chinese wav2vec2 model).
    align_python: str = "./data/tools/indextts-venv/Scripts/python.exe"
    align_script: str = "./scripts/runtime/align_words.py"
    align_repo: str = "./data/tools/IndexTTS2"
    align_model_dir: str = "./data/assets/voice/align/wav2vec2-chinese"
    align_device: str = "cuda"
    align_level: Literal["sentence", "char"] = "sentence"
    align_use_normalizer: bool = True
    align_stop_tts: bool = True
    align_timeout_s: float = 1800.0

    # M4.3 QC: deterministic rules first, then DeepSeek multimodal on frames.
    qc_auto_run: bool = True
    qc_frame_scale: int = 1280
    qc_frames_per_shot: int = 2
    qc_max_frames: int = 60
    qc_vision_batch: int = 4
    qc_vision_timeout_s: float = 180.0
    qc_vision_max_tokens: int = 2000
    # Vision findings are advisory by default; deterministic rule errors block.
    qc_vision_blocking: bool = False

    # M5 ops: mark RUNNING nodes without heartbeat as failed so they can resume.
    reconciler_stale_s: int = 1800
    reconciler_interval_s: int = 60
    package_dir: str = "./tmp/packages"

    celery_task_always_eager: bool = False
    outbox_poll_interval_s: float = 5.0
    render_dir: str = "./tmp/renders"
    renderer_version: str = "m5.6-overlay"
    asset_storage: str = "local"
    asset_root: str = "./data/assets"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
