"""add is_completed and payment_amount

Revision ID: 20251203_142506
Revises: 
Create Date: 2025-12-03 14:25:06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251203_142506'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_completed and payment_amount columns to appointments table."""
    op.add_column('appointments', sa.Column('is_completed', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('appointments', sa.Column('payment_amount', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove is_completed and payment_amount columns from appointments table."""
    op.drop_column('appointments', 'payment_amount')
    op.drop_column('appointments', 'is_completed')
