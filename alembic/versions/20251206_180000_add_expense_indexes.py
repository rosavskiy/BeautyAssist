"""Add indexes for expense queries optimization

Revision ID: 20251206_180000
Revises: 20251203_170000
Create Date: 2024-12-06 18:00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '20251206_180000'
down_revision = '1bac6889eeb7'  # Latest migration in production
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add indexes for expense date queries."""
    # Single index on expense_date for date range queries
    op.create_index(
        'ix_expenses_expense_date',
        'expenses',
        ['expense_date'],
        unique=False
    )
    
    # Composite index on (master_id, expense_date) for filtered queries
    # This index will be used for most common query pattern:
    # WHERE master_id = ? AND expense_date BETWEEN ? AND ?
    op.create_index(
        'ix_expenses_master_date',
        'expenses',
        ['master_id', 'expense_date'],
        unique=False
    )


def downgrade() -> None:
    """Remove expense indexes."""
    op.drop_index('ix_expenses_master_date', table_name='expenses')
    op.drop_index('ix_expenses_expense_date', table_name='expenses')
