"""Mako template for alembic migrations."""
"""add_referrals_tracking_table

Revision ID: 4c7e7d471023
Revises: 73db78e76920
Create Date: 2025-12-05 01:18:21.238023+03:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c7e7d471023'
down_revision: Union[str, None] = '73db78e76920'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create referrals tracking table
    op.create_table(
        'referrals',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('referrer_id', sa.BigInteger(), nullable=False, comment='Master who referred'),
        sa.Column('referred_id', sa.BigInteger(), nullable=False, comment='Master who was referred'),
        sa.Column('status', sa.String(length=20), nullable=False, comment='pending/activated/expired'),
        sa.Column('reward_given', sa.Boolean(), nullable=False, server_default='false', comment='Whether reward was given'),
        sa.Column('reward_days', sa.Integer(), nullable=False, server_default='7', comment='Days added to subscription'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('activated_at', sa.TIMESTAMP(timezone=True), nullable=True, comment='When referral activated subscription'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['referrer_id'], ['masters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['referred_id'], ['masters.id'], ondelete='CASCADE'),
    )
    
    # Create indexes
    op.create_index(op.f('ix_referrals_referrer_id'), 'referrals', ['referrer_id'], unique=False)
    op.create_index(op.f('ix_referrals_referred_id'), 'referrals', ['referred_id'], unique=False)
    op.create_index(op.f('ix_referrals_status'), 'referrals', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_referrals_status'), table_name='referrals')
    op.drop_index(op.f('ix_referrals_referred_id'), table_name='referrals')
    op.drop_index(op.f('ix_referrals_referrer_id'), table_name='referrals')
    op.drop_table('referrals')
