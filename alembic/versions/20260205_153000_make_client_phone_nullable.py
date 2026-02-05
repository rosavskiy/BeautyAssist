"""make client phone nullable

Revision ID: 8f3c2a1b5d7e
Revises: a5e51ae973ef
Create Date: 2026-02-05 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f3c2a1b5d7e'
down_revision: Union[str, None] = 'a5e51ae973ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make phone column nullable for clients imported from Telegram
    op.alter_column('clients', 'phone',
               existing_type=sa.VARCHAR(length=20),
               nullable=True)


def downgrade() -> None:
    # Revert to non-nullable (will fail if there are NULL values)
    op.alter_column('clients', 'phone',
               existing_type=sa.VARCHAR(length=20),
               nullable=False)
