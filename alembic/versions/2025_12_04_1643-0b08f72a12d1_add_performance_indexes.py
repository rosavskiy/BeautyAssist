"""Mako template for alembic migrations."""
"""add_performance_indexes

Revision ID: 0b08f72a12d1
Revises: 369c7baa9efb
Create Date: 2025-12-04 16:43:18.920628+03:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0b08f72a12d1'
down_revision: Union[str, None] = '369c7baa9efb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add composite indexes for better query performance."""
    
    # Appointments: часто используемые комбинации для выборки
    # 1. Поиск записей мастера по дате и статусу
    op.create_index(
        'ix_appointments_master_status_time',
        'appointments',
        ['master_id', 'status', 'start_time'],
        unique=False
    )
    
    # 2. Поиск записей клиента по статусу (для "Мои записи")
    op.create_index(
        'ix_appointments_client_status_time',
        'appointments',
        ['client_id', 'status', 'start_time'],
        unique=False
    )
    
    # 3. Проверка конфликтов времени (check_time_conflict)
    op.create_index(
        'ix_appointments_master_time_range',
        'appointments',
        ['master_id', 'start_time', 'end_time'],
        unique=False
    )
    
    # Reminders: поиск напоминаний для отправки
    # 4. Запланированные напоминания в определенное время
    op.create_index(
        'ix_reminders_status_scheduled_time',
        'reminders',
        ['status', 'scheduled_time'],
        unique=False
    )
    
    # Clients: поиск клиентов мастера
    # 5. Составной индекс для поиска по telegram_id и master_id
    op.create_index(
        'ix_clients_master_telegram',
        'clients',
        ['master_id', 'telegram_id'],
        unique=False
    )
    
    # 6. Поиск по телефону в рамках мастера (предотвращение дублей)
    op.create_index(
        'ix_clients_master_phone',
        'clients',
        ['master_id', 'phone'],
        unique=False
    )


def downgrade() -> None:
    """Remove composite indexes."""
    op.drop_index('ix_clients_master_phone', table_name='clients')
    op.drop_index('ix_clients_master_telegram', table_name='clients')
    op.drop_index('ix_reminders_status_scheduled_time', table_name='reminders')
    op.drop_index('ix_appointments_master_time_range', table_name='appointments')
    op.drop_index('ix_appointments_client_status_time', table_name='appointments')
    op.drop_index('ix_appointments_master_status_time', table_name='appointments')
