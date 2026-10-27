from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Position = Literal["left", "right", "center"]
CardType = Literal["chat_bubble", "terminal", "browser", "icon", "pure_text"]


class CharacterSpec(BaseModel):
    image: str
    position: Position = "left"
    height_px: int = 1000
    motion: Literal["none", "idle_breathe"] = "idle_breathe"


class CardSpec(BaseModel):
    type: CardType = "chat_bubble"
    style: str = "ai_reply"
    text: str = ""


class ShotSpec(BaseModel):
    shot_id: str
    seq: int = Field(ge=1)
    section: str
    narration: str
    duration_ms: int = Field(ge=500, le=15000)
    character: CharacterSpec | None = None
    card: CardSpec | None = None
    bg: str | None = None
    floor: str | None = None


class EpisodeSpec(BaseModel):
    title: str
    fps: int = Field(default=25, ge=1, le=60)
    width: int = 1920
    height: int = 1080
    section_labels: list[str] = Field(min_length=1)
    background: str
    floor: str
    watermark: str = "Roxy Pipeline · DEMO"
    shots: list[ShotSpec] = Field(min_length=1)

    @field_validator("section_labels")
    @classmethod
    def labels_must_be_unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("section_labels must be unique")
        return value

    @model_validator(mode="after")
    def check_shots(self) -> "EpisodeSpec":
        seqs = [shot.seq for shot in self.shots]
        if seqs != list(range(1, len(seqs) + 1)):
            raise ValueError("shot.seq must be contiguous starting at 1")
        labels = set(self.section_labels)
        for shot in self.shots:
            if shot.section not in labels:
                raise ValueError(f"unknown section: {shot.section}")
        return self
