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
    move: Literal[
        "none",
        "slide_in_left",
        "slide_in_right",
        "shift_left",
        "shift_right",
    ] = "none"
    anchor_x: float | None = Field(default=None, ge=0.0, le=1.0)
    anchor_y: int | None = Field(default=None, ge=0)
    scale: float = Field(default=1.0, gt=0.0, le=2.0)


class CardSpec(BaseModel):
    type: CardType = "chat_bubble"
    style: str = "ai_reply"
    text: str = ""


class CharTiming(BaseModel):
    text: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)


class OverlaySpec(BaseModel):
    image: str
    position: Literal["left", "center", "right"] = "center"
    width_px: int = Field(default=420, ge=40, le=1900)
    bottom: int = Field(default=120, ge=0, le=1080)
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    blend: Literal["normal", "multiply"] = "normal"


class ShotSpec(BaseModel):
    shot_id: str
    seq: int = Field(ge=1)
    section: str
    narration: str
    duration_ms: int = Field(ge=500, le=15000)
    character: CharacterSpec | None = None
    card: CardSpec | None = None
    overlay: OverlaySpec | None = None
    bg: str | None = None
    floor: str | None = None
    template_version: str = "v1"
    # Character timings relative to shot start; populated after M4.2 alignment.
    char_timings: list[CharTiming] = Field(default_factory=list)


class RemotionShotSpec(BaseModel):
    composition_id: str
    code_hash: str


class RemotionRenderSpec(BaseModel):
    work_dir: str
    version: str
    image_digest: str | None = None
    shots: dict[str, RemotionShotSpec] = Field(default_factory=dict)


class EpisodeSpec(BaseModel):
    title: str
    fps: int = Field(default=25, ge=1, le=60)
    width: int = 1920
    height: int = 1080
    section_labels: list[str] = Field(min_length=1)
    alignment_level: Literal["sentence", "char"] = "char"
    renderer: Literal["playwright", "remotion"] = "playwright"
    remotion: RemotionRenderSpec | None = None
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
