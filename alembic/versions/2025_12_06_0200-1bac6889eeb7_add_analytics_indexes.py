"""Mako template for alembic migrations."""
"""add_analytics_indexes

Revision ID: 1bac6889eeb7
Revises: 4c7e7d471023
Create Date: 2025-12-06 02:00:29.163718+03:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1bac6889eeb7'
down_revision: Union[str, None] = '4c7e7d471023'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add indexes for analytics queries optimization."""
    
    # Masters: для cohort analysis и retention расчётов
    # 1. Индекс на дату создания (группировка по неделям/месяцам)
    op.create_index(
        'ix_masters_created_at',
        'masters',
        ['created_at'],
        unique=False
    )
    
    # 2. Составной индекс для funnel analysis (onboarding + creation date)
    op.create_index(
        'ix_masters_onboarded_created',
        'masters',
        ['is_onboarded', 'created_at'],
        unique=False
    )
    
    # Appointments: для расчёта активности в когортах
    # 3. Составной индекс master + дата создания (когда запись создана)
    op.create_index(
        'ix_appointments_master_created',
        'appointments',
        ['master_id', 'created_at'],
        unique=False
    )


def downgrade() -> None:
    """Remove analytics indexes."""
    op.drop_index('ix_appointments_master_created', table_name='appointments')
    op.drop_index('ix_masters_onboarded_created', table_name='masters')
    op.drop_index('ix_masters_created_at', table_name='masters')
