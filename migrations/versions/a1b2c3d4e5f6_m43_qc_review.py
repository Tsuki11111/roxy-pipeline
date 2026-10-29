"""M4.3 QC reviews and episode summary

Revision ID: a1b2c3d4e5f6
Revises: f7b8c9d0e1f2
Create Date: 2026-10-29 17:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("episode", sa.Column("qc_meta", sa.JSON(), nullable=True))
    op.create_table(
        "review",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("episode_id", sa.String(length=36), nullable=False),
        sa.Column("check_item", sa.String(length=100), nullable=False),
        sa.Column(
            "level",
            sa.Enum(
                "PASS",
                "WARNING",
                "ERROR",
                "MANUAL",
                name="reviewlevel",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("evidence_path", sa.String(length=500), nullable=True),
        sa.Column("resolved_by", sa.String(length=100), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["episode_id"], ["episode.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_review_episode_id"), "review", ["episode_id"], unique=False
    )
    op.create_index(op.f("ix_review_level"), "review", ["level"], unique=False)
    op.create_index(
        "ix_review_episode_level", "review", ["episode_id", "level"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_review_episode_level", table_name="review")
    op.drop_index(op.f("ix_review_level"), table_name="review")
    op.drop_index(op.f("ix_review_episode_id"), table_name="review")
    op.drop_table("review")
    op.drop_column("episode", "qc_meta")
