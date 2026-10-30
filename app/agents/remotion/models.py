from __future__ import annotations

from pydantic import BaseModel, Field


class ShotCodeOutput(BaseModel):
    schema_version: str = "1"
    component_name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=20)
    summary: str = ""


class RemotionShotMeta(BaseModel):
    composition_id: str
    code_hash: str
    code_path: str
    status: str = "PENDING"
    error: str | None = None
    input_hash: str = ""
    prompt_hash: str | None = None
    model: str | None = None
    image_digest: str | None = None


class RemotionEpisodeMeta(BaseModel):
    enabled: bool = False
    status: str = "idle"
    work_dir: str | None = None
    version: str | None = None
    image_digest: str | None = None
    model: str | None = None
    skill_hash: str | None = None
    prompt_hash: str | None = None
    generated_at: str | None = None
    shots: dict[str, RemotionShotMeta] = Field(default_factory=dict)
