"""Add face_center_x and face_center_y to photos table.

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
    op.add_column("photos", sa.Column("face_center_x", sa.Float(), nullable=True))
    op.add_column("photos", sa.Column("face_center_y", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("photos", "face_center_y")
    op.drop_column("photos", "face_center_x")
