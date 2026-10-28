"""M3 storyboard meta

Revision ID: d4e5f6a7b8c9
Revises: b7e2c9a14d10
Create Date: 2026-10-28 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "b7e2c9a14d10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("episode", sa.Column("storyboard_meta", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("episode", "storyboard_meta")
