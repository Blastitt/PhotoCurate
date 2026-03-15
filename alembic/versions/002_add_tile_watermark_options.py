"""Add tile watermark options to tenant_branding.

Revision ID: 002
Revises: 001
Create Date: 2026-03-15

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenant_branding",
        sa.Column("watermark_tile_rotation", sa.Float(), server_default="45.0", nullable=False),
    )
    op.add_column(
        "tenant_branding",
        sa.Column("watermark_tile_spacing", sa.Float(), server_default="0.5", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("tenant_branding", "watermark_tile_spacing")
    op.drop_column("tenant_branding", "watermark_tile_rotation")
