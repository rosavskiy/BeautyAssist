"""change last_visit to timestamptz

Revision ID: 20251203_160000
Revises: 20251203_142506
Create Date: 2025-12-03 16:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251203_160000'
down_revision: Union[str, None] = '20251203_142506'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change last_visit column type to TIMESTAMP WITH TIME ZONE."""
    # PostgreSQL can convert TIMESTAMP to TIMESTAMPTZ automatically
    op.alter_column(
        'clients',
        'last_visit',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_nullable=True,
        postgresql_using='last_visit AT TIME ZONE \'UTC\''
    )


def downgrade() -> None:
    """Change last_visit column type back to TIMESTAMP WITHOUT TIME ZONE."""
    op.alter_column(
        'clients',
        'last_visit',
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True
    )
