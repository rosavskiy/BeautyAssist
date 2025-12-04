"""Mako template for alembic migrations."""
"""add_client_comment_to_appointments

Revision ID: 369c7baa9efb
Revises: 20251203_170000
Create Date: 2025-12-03 22:41:06.605931+03:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '369c7baa9efb'
down_revision: Union[str, None] = '20251203_170000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add client_comment column to appointments table
    op.add_column('appointments', sa.Column('client_comment', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove client_comment column
    op.drop_column('appointments', 'client_comment')
