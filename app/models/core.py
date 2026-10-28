from __future__ import annotations

import enum
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def new_id() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EpisodeStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    TOPIC_CONFIRMED = "TOPIC_CONFIRMED"
    SCRIPTING = "SCRIPTING"
    SCRIPT_REVIEW = "SCRIPT_REVIEW"
    STORYBOARDING = "STORYBOARDING"
    VOICING = "VOICING"
    ALIGNING = "ALIGNING"
    RENDERING = "RENDERING"
    QC = "QC"
    READY = "READY"
    PUBLISHED = "PUBLISHED"
    CANCELLED = "CANCELLED"


class NodeStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"
    STALE = "STALE"


class OutboxStatus(str, enum.Enum):
    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"
    FAILED = "FAILED"


class Series(Base):
    __tablename__ = "series"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    voice_profile: Mapped[dict] = mapped_column(JSON, default=dict)
    section_labels: Mapped[list] = mapped_column(JSON, default=list)
    character_pack_id: Mapped[str] = mapped_column(String(100), default="roxy")
    watermark: Mapped[str] = mapped_column(String(200), default="")
    template_version: Mapped[str] = mapped_column(String(50), default="v1")
    non_commercial: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    episodes: Mapped[list["Episode"]] = relationship(back_populates="series")


class Episode(Base):
    __tablename__ = "episode"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    series_id: Mapped[str] = mapped_column(
        ForeignKey("series.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    topic: Mapped[str] = mapped_column(Text, default="")
    target_duration_s: Mapped[int] = mapped_column(Integer, default=600)
    status: Mapped[EpisodeStatus] = mapped_column(
        SAEnum(EpisodeStatus, native_enum=False, length=32),
        default=EpisodeStatus.DRAFT,
        index=True,
    )
    health: Mapped[str] = mapped_column(String(20), default="OK")
    current_node: Mapped[str | None] = mapped_column(String(100), nullable=True)
    output_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # M1.2 bridge: a hand-written render spec until storyboard/TTS generate shots.
    render_spec: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    series: Mapped[Series] = relationship(back_populates="episodes")
    script_lines: Mapped[list["ScriptLine"]] = relationship(
        back_populates="episode", cascade="all, delete-orphan"
    )
    shots: Mapped[list["Shot"]] = relationship(
        back_populates="episode", cascade="all, delete-orphan"
    )
    node_runs: Mapped[list["NodeRun"]] = relationship(
        back_populates="episode", cascade="all, delete-orphan"
    )


class ScriptLine(Base):
    __tablename__ = "script_line"
    __table_args__ = (
        UniqueConstraint("episode_id", "seq", name="uq_script_line_episode_seq"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    episode_id: Mapped[str] = mapped_column(
        ForeignKey("episode.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str] = mapped_column(String(30), default="narrator")
    section: Mapped[str] = mapped_column(String(100), default="")
    text: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)

    episode: Mapped[Episode] = relationship(back_populates="script_lines")


class Shot(Base):
    __tablename__ = "shot"
    __table_args__ = (
        UniqueConstraint("episode_id", "seq", name="uq_shot_episode_seq"),
        Index("ix_shot_cache_key", "cache_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    episode_id: Mapped[str] = mapped_column(
        ForeignKey("episode.id", ondelete="CASCADE"), index=True
    )
    script_line_id: Mapped[str] = mapped_column(
        ForeignKey("script_line.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer, default=3000)
    card_type: Mapped[str] = mapped_column(String(30), default="chat_bubble")
    card_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    character_image: Mapped[str | None] = mapped_column(String(300), nullable=True)
    character_position: Mapped[str] = mapped_column(String(20), default="left")
    bg: Mapped[str] = mapped_column(String(100), default="paper")
    transition: Mapped[str] = mapped_column(String(30), default="cut")
    cache_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    template_version: Mapped[str] = mapped_column(String(50), default="v1")

    episode: Mapped[Episode] = relationship(back_populates="shots")


class NodeRun(Base):
    __tablename__ = "node_run"
    __table_args__ = (
        UniqueConstraint(
            "episode_id", "node_key", "input_hash", name="uq_node_run_input"
        ),
        Index("ix_node_run_status_heartbeat", "status", "heartbeat_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    episode_id: Mapped[str] = mapped_column(
        ForeignKey("episode.id", ondelete="CASCADE"), index=True
    )
    node_key: Mapped[str] = mapped_column(String(100))
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[NodeStatus] = mapped_column(
        SAEnum(NodeStatus, native_enum=False, length=20),
        default=NodeStatus.PENDING,
        index=True,
    )
    input_hash: Mapped[str] = mapped_column(String(128), default="")
    cache_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    output_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)

    episode: Mapped[Episode] = relationship(back_populates="node_runs")


class OutboxEvent(Base):
    __tablename__ = "outbox_event"
    __table_args__ = (
        Index("ix_outbox_status_available", "status", "available_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    episode_id: Mapped[str | None] = mapped_column(
        ForeignKey("episode.id", ondelete="CASCADE"), index=True, nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[OutboxStatus] = mapped_column(
        SAEnum(OutboxStatus, native_enum=False, length=20),
        default=OutboxStatus.PENDING,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
