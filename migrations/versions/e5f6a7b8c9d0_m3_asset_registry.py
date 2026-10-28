"""M3 asset registry

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-28 17:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "asset",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "CHARACTER",
                "BACKGROUND",
                "PROP",
                "ICON",
                "COVER",
                name="assettype",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("reuse_key", sa.String(length=200), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("mime", sa.String(length=100), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("seed", sa.String(length=100), nullable=True),
        sa.Column("reference", sa.String(length=500), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "CANDIDATE",
                "APPROVED",
                "REJECTED",
                name="assetstatus",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_asset_type"), "asset", ["type"], unique=False)
    op.create_index(op.f("ix_asset_reuse_key"), "asset", ["reuse_key"], unique=True)
    op.create_index(op.f("ix_asset_status"), "asset", ["status"], unique=False)
    op.create_index("ix_asset_type_status", "asset", ["type", "status"], unique=False)
    op.create_index("ix_asset_checksum", "asset", ["checksum"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_asset_checksum", table_name="asset")
    op.drop_index("ix_asset_type_status", table_name="asset")
    op.drop_index(op.f("ix_asset_status"), table_name="asset")
    op.drop_index(op.f("ix_asset_reuse_key"), table_name="asset")
    op.drop_index(op.f("ix_asset_type"), table_name="asset")
    op.drop_table("asset")
