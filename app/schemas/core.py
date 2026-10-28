from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.agents.script_validation import ValidationResult
from app.models.core import EpisodeStatus, NodeStatus


class HealthResponse(BaseModel):
    status: str
    env: str
    database: str


class SeriesCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    voice_profile: dict = Field(default_factory=dict)
    section_labels: list[str] = Field(default_factory=list)
    character_pack_id: str = "roxy"
    watermark: str = ""
    template_version: str = "v1"
    non_commercial: bool = True


class SeriesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    voice_profile: dict
    section_labels: list[str]
    character_pack_id: str
    watermark: str
    template_version: str
    non_commercial: bool
    created_at: datetime


class EpisodeCreate(BaseModel):
    series_id: str
    title: str = Field(min_length=1, max_length=300)
    topic: str = ""
    target_duration_s: int = Field(default=600, ge=30, le=3600)


class EpisodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    series_id: str
    title: str
    topic: str
    target_duration_s: int
    status: EpisodeStatus
    health: str
    current_node: str | None
    output_path: str | None
    render_spec: dict | None
    script_meta: dict | None
    version: int
    created_at: datetime
    updated_at: datetime


class EpisodeActionAccepted(BaseModel):
    episode_id: str
    status: EpisodeStatus
    node_key: str
    operation_id: str


class ScriptLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    episode_id: str
    seq: int
    speaker: str
    section: str
    text: str
    char_count: int
    version: int


class ShotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    episode_id: str
    script_line_id: str
    seq: int
    duration_ms: int
    card_type: str
    card_payload: dict
    character_image: str | None
    character_position: str
    bg: str
    transition: str
    cache_key: str | None
    template_version: str


class NodeRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    episode_id: str
    node_key: str
    parent_id: str | None
    status: NodeStatus
    input_hash: str
    cache_key: str | None
    attempt: int
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    heartbeat_at: datetime | None
    output_ref: str | None


class ScriptRead(BaseModel):
    episode_id: str
    status: EpisodeStatus
    meta: dict | None
    lines: list[ScriptLineRead]
    validation: ValidationResult


class ScriptLineUpdate(BaseModel):
    text: str = Field(min_length=1, max_length=200)


class ScriptLineUpdateResult(BaseModel):
    line: ScriptLineRead
    validation: ValidationResult
