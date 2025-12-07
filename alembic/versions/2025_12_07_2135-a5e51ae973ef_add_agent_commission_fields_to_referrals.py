"""Mako template for alembic migrations."""
"""add_agent_commission_fields_to_referrals

Revision ID: a5e51ae973ef
Revises: 20251206_180000
Create Date: 2025-12-07 21:35:50.165320+03:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a5e51ae973ef'
down_revision: Union[str, None] = '20251206_180000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add agent commission fields to referrals table
    op.add_column('referrals', sa.Column('commission_percent', sa.Integer(), nullable=False, server_default='10', comment='Commission percentage for agent (default 10%)'))
    op.add_column('referrals', sa.Column('commission_stars', sa.Integer(), nullable=False, server_default='0', comment='Commission amount in Telegram Stars'))
    op.add_column('referrals', sa.Column('payout_status', sa.String(length=20), nullable=False, server_default='pending', comment='pending/sent/failed'))
    op.add_column('referrals', sa.Column('payout_transaction_id', sa.String(length=255), nullable=True, comment='Telegram payment transaction ID'))
    op.add_column('referrals', sa.Column('payout_sent_at', sa.TIMESTAMP(timezone=True), nullable=True, comment='When commission was paid to agent'))
    
    # Create index on payout_status
    op.create_index('ix_referrals_payout_status', 'referrals', ['payout_status'], unique=False)


def downgrade() -> None:
    # Drop index and columns
    op.drop_index('ix_referrals_payout_status', table_name='referrals')
    op.drop_column('referrals', 'payout_sent_at')
    op.drop_column('referrals', 'payout_transaction_id')
    op.drop_column('referrals', 'payout_status')
    op.drop_column('referrals', 'commission_stars')
    op.drop_column('referrals', 'commission_percent')
