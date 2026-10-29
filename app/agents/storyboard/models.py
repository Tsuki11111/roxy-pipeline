from __future__ import annotations

from pydantic import BaseModel, Field


class ShotDraft(BaseModel):
    seq: int
    line_seq: int
    line_id: str | None = None
    section: str
    speaker: str = "narrator"
    text: str
    duration_ms: int
    card_type: str = "chat_bubble"
    card_style: str = ""
    character_image: str | None = None
    character_position: str = "left"
    bg: str = "paper"
    transition: str = "cut"
    motion: str = "idle_breathe"


class RhythmReport(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    shot_count: int
    avg_duration_ms: float
    card_distribution: dict[str, int] = Field(default_factory=dict)
    character_ratio: float
    section_last_cards: dict[str, str] = Field(default_factory=dict)
