"""M4.1 line audio and episode voice track

Revision ID: f7b8c9d0e1f2
Revises: e5f6a7b8c9d0
Create Date: 2026-10-29 15:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7b8c9d0e1f2"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "episode", sa.Column("audio_path", sa.String(length=500), nullable=True)
    )
    op.add_column("episode", sa.Column("audio_meta", sa.JSON(), nullable=True))

    op.create_table(
        "line_audio",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("episode_id", sa.String(length=36), nullable=False),
        sa.Column("script_line_id", sa.String(length=36), nullable=False),
        sa.Column("line_version", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.String(length=30), nullable=False),
        sa.Column("text_hash", sa.String(length=64), nullable=False),
        sa.Column("voice_key", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("ref_audio", sa.String(length=500), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("sample_rate", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["episode_id"], ["episode.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["script_line_id"], ["script_line.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "script_line_id",
            "text_hash",
            "voice_key",
            name="uq_line_audio_text_voice",
        ),
    )
    op.create_index(
        op.f("ix_line_audio_episode_id"), "line_audio", ["episode_id"], unique=False
    )
    op.create_index(
        op.f("ix_line_audio_script_line_id"),
        "line_audio",
        ["script_line_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_line_audio_script_line_id"), table_name="line_audio"
    )
    op.drop_index(op.f("ix_line_audio_episode_id"), table_name="line_audio")
    op.drop_table("line_audio")
    op.drop_column("episode", "audio_meta")
    op.drop_column("episode", "audio_path")
