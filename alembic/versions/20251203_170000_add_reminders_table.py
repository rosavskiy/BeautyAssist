"""add reminders table

Revision ID: 20251203_170000
Revises: 20251203_160000
Create Date: 2025-12-03 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251203_170000'
down_revision: Union[str, None] = '20251203_160000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create reminders table
    op.create_table(
        'reminders',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('appointment_id', sa.BigInteger(), nullable=False),
        sa.Column('reminder_type', sa.String(length=20), nullable=False),
        sa.Column('channel', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('scheduled_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_reminders_appointment_id', 'reminders', ['appointment_id'])
    op.create_index('ix_reminders_scheduled_time', 'reminders', ['scheduled_time'])
    
    # Create foreign key
    op.create_foreign_key(
        'fk_reminders_appointment_id',
        'reminders', 'appointments',
        ['appointment_id'], ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    # Drop table and indexes
    op.drop_table('reminders')
