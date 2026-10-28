"""M1.2 outbox and render spec

Revision ID: 9c1f4e7a2b30
Revises: 08b2efde929a
Create Date: 2026-10-28 14:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9c1f4e7a2b30"
down_revision: str | None = "08b2efde929a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("episode", sa.Column("render_spec", sa.JSON(), nullable=True))
    op.create_table(
        "outbox_event",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("episode_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "DISPATCHED",
                "FAILED",
                name="outboxstatus",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["episode_id"], ["episode.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_outbox_event_episode_id"), "outbox_event", ["episode_id"], unique=False
    )
    op.create_index(
        op.f("ix_outbox_event_event_type"), "outbox_event", ["event_type"], unique=False
    )
    op.create_index(
        op.f("ix_outbox_event_status"), "outbox_event", ["status"], unique=False
    )
    op.create_index(
        "ix_outbox_status_available",
        "outbox_event",
        ["status", "available_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_status_available", table_name="outbox_event")
    op.drop_index(op.f("ix_outbox_event_status"), table_name="outbox_event")
    op.drop_index(op.f("ix_outbox_event_event_type"), table_name="outbox_event")
    op.drop_index(op.f("ix_outbox_event_episode_id"), table_name="outbox_event")
    op.drop_table("outbox_event")
    op.drop_column("episode", "render_spec")
