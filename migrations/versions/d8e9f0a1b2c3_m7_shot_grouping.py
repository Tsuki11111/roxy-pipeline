"""M7 shot grouping, scene continuity and AI duration estimate

Revision ID: d8e9f0a1b2c3
Revises: c3d4e5f6a7b8
Create Date: 2026-11-01 14:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "d8e9f0a1b2c3"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "episode", sa.Column("estimated_duration_s", sa.Integer(), nullable=True)
    )
    op.add_column(
        "episode",
        sa.Column(
            "duration_source",
            sa.String(length=20),
            nullable=False,
            server_default="legacy",
        ),
    )
    op.execute(
        "UPDATE episode SET estimated_duration_s = target_duration_s "
        "WHERE estimated_duration_s IS NULL"
    )

    op.add_column(
        "shot", sa.Column("continuity_group", sa.String(length=100), nullable=True)
    )
    op.add_column("shot", sa.Column("scene_meta", sa.JSON(), nullable=True))

    op.create_table(
        "shot_line",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("episode_id", sa.String(length=36), nullable=False),
        sa.Column("shot_id", sa.String(length=36), nullable=False),
        sa.Column("script_line_id", sa.String(length=36), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["episode_id"], ["episode.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shot_id"], ["shot.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["script_line_id"], ["script_line.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shot_id", "seq", name="uq_shot_line_shot_seq"),
        sa.UniqueConstraint("script_line_id", name="uq_shot_line_script_line"),
    )
    op.create_index(
        op.f("ix_shot_line_episode_id"), "shot_line", ["episode_id"], unique=False
    )
    op.create_index(
        op.f("ix_shot_line_shot_id"), "shot_line", ["shot_id"], unique=False
    )
    op.create_index(
        op.f("ix_shot_line_script_line_id"),
        "shot_line",
        ["script_line_id"],
        unique=False,
    )

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, episode_id, script_line_id FROM shot "
            "WHERE script_line_id IS NOT NULL"
        )
    ).fetchall()
    if rows:
        now = datetime.now(timezone.utc)
        bind.execute(
            sa.text(
                "INSERT INTO shot_line "
                "(id, episode_id, shot_id, script_line_id, seq, created_at) "
                "VALUES (:id, :episode_id, :shot_id, :script_line_id, 1, :created_at)"
            ),
            [
                {
                    "id": str(uuid4()),
                    "episode_id": row.episode_id,
                    "shot_id": row.id,
                    "script_line_id": row.script_line_id,
                    "created_at": now,
                }
                for row in rows
            ],
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_shot_line_script_line_id"), table_name="shot_line")
    op.drop_index(op.f("ix_shot_line_shot_id"), table_name="shot_line")
    op.drop_index(op.f("ix_shot_line_episode_id"), table_name="shot_line")
    op.drop_table("shot_line")
    op.drop_column("shot", "scene_meta")
    op.drop_column("shot", "continuity_group")
    op.drop_column("episode", "duration_source")
    op.drop_column("episode", "estimated_duration_s")