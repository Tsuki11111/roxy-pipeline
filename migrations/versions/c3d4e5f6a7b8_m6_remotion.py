"""M6 Remotion per-shot codegen metadata

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-30 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("episode", sa.Column("remotion_meta", sa.JSON(), nullable=True))
    op.create_table(
        "remotion_shot",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("episode_id", sa.String(length=36), nullable=False),
        sa.Column("shot_id", sa.String(length=36), nullable=False),
        sa.Column("composition_id", sa.String(length=100), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("code_path", sa.String(length=500), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("prompt_hash", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("image_digest", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["episode_id"], ["episode.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shot_id"], ["shot.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shot_id", name="uq_remotion_shot_shot"),
    )
    op.create_index(
        op.f("ix_remotion_shot_episode_id"),
        "remotion_shot",
        ["episode_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_remotion_shot_shot_id"),
        "remotion_shot",
        ["shot_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_remotion_shot_shot_id"), table_name="remotion_shot")
    op.drop_index(op.f("ix_remotion_shot_episode_id"), table_name="remotion_shot")
    op.drop_table("remotion_shot")
    op.drop_column("episode", "remotion_meta")
