"""M2 script meta

Revision ID: b7e2c9a14d10
Revises: 9c1f4e7a2b30
Create Date: 2026-10-28 15:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e2c9a14d10"
down_revision: str | None = "9c1f4e7a2b30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("episode", sa.Column("script_meta", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("episode", "script_meta")
