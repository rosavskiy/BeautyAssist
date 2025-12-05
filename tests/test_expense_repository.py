"""Unit tests for ExpenseRepository."""
import pytest
from datetime import datetime, timedelta

from database.repositories.expense import ExpenseRepository
from database.models import Expense


@pytest.mark.asyncio
async def test_create_expense(db_session, sample_master):
    """Test creating a new expense."""
    repo = ExpenseRepository(db_session)
    
    expense = await repo.create(
        master_id=sample_master.id,
        category="Supplies",
        amount=1500,
        description="Nail polish",
        expense_date=datetime.now(),
    )
    
    assert expense.id is not None
    assert expense.master_id == sample_master.id
    assert expense.category == "Supplies"
    assert expense.amount == 1500
    assert expense.description == "Nail polish"


@pytest.mark.asyncio
async def test_get_by_id(db_session, sample_master):
    """Test retrieving expense by ID."""
    repo = ExpenseRepository(db_session)
    
    created = await repo.create(
        master_id=sample_master.id,
        category="Rent",
        amount=20000,
        expense_date=datetime.now(),
    )
    
    retrieved = await repo.get_by_id(created.id)
    
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.category == "Rent"


@pytest.mark.asyncio
async def test_get_by_master(db_session, sample_master):
    """Test retrieving expenses for master."""
    repo = ExpenseRepository(db_session)
    
    # Create multiple expenses
    await repo.create(
        master_id=sample_master.id,
        category="Supplies",
        amount=1000,
        expense_date=datetime.now(),
    )
    
    await repo.create(
        master_id=sample_master.id,
        category="Rent",
        amount=20000,
        expense_date=datetime.now(),
    )
    
    expenses = await repo.get_by_master(sample_master.id)
    
    assert len(expenses) >= 2
    assert all(e.master_id == sample_master.id for e in expenses)


@pytest.mark.asyncio
async def test_get_by_master_with_date_filter(db_session, sample_master):
    """Test filtering expenses by date range."""
    repo = ExpenseRepository(db_session)
    
    today = datetime.now()
    
    # Create expense today
    await repo.create(
        master_id=sample_master.id,
        category="Supplies",
        amount=1000,
        expense_date=today,
    )
    
    # Create expense 10 days ago
    await repo.create(
        master_id=sample_master.id,
        category="Old expense",
        amount=5000,
        expense_date=today - timedelta(days=10),
    )
    
    # Get last 7 days
    expenses = await repo.get_by_master(
        sample_master.id,
        start_date=today - timedelta(days=7),
        end_date=today + timedelta(days=1),
    )
    
    assert len(expenses) == 1
    assert expenses[0].category == "Supplies"


@pytest.mark.asyncio
async def test_get_by_master_with_category_filter(db_session, sample_master):
    """Test filtering expenses by category."""
    repo = ExpenseRepository(db_session)
    
    # Create expenses with different categories
    await repo.create(
        master_id=sample_master.id,
        category="Supplies",
        amount=1000,
        expense_date=datetime.now(),
    )
    
    await repo.create(
        master_id=sample_master.id,
        category="Rent",
        amount=20000,
        expense_date=datetime.now(),
    )
    
    await repo.create(
        master_id=sample_master.id,
        category="Supplies",
        amount=1500,
        expense_date=datetime.now(),
    )
    
    # Get only Supplies
    supplies = await repo.get_by_master(
        sample_master.id,
        category="Supplies"
    )
    
    assert len(supplies) == 2
    assert all(e.category == "Supplies" for e in supplies)


@pytest.mark.asyncio
async def test_update_expense(db_session, sample_master):
    """Test updating expense."""
    repo = ExpenseRepository(db_session)
    
    expense = await repo.create(
        master_id=sample_master.id,
        category="Supplies",
        amount=1000,
        expense_date=datetime.now(),
    )
    
    expense.amount = 1500
    expense.description = "Updated description"
    
    updated = await repo.update(expense)
    
    assert updated.amount == 1500
    assert updated.description == "Updated description"


@pytest.mark.asyncio
async def test_delete_expense(db_session, sample_master):
    """Test deleting expense."""
    repo = ExpenseRepository(db_session)
    
    expense = await repo.create(
        master_id=sample_master.id,
        category="Supplies",
        amount=1000,
        expense_date=datetime.now(),
    )
    
    expense_id = expense.id
    
    await repo.delete(expense_id)
    
    # Try to retrieve deleted expense
    deleted = await repo.get_by_id(expense_id)
    assert deleted is None


@pytest.mark.asyncio
async def test_expense_isolation_between_masters(db_session):
    """Test that expenses are properly isolated between masters."""
    from database.models import Master
    
    repo = ExpenseRepository(db_session)
    
    # Create two masters
    master1 = Master(
        telegram_id=111111111,
        name="Master 1",
        phone="+79991111111",
        city="Москва",
        timezone="Europe/Moscow",
        is_onboarded=True,
        referral_code="MASTER1",
    )
    db_session.add(master1)
    
    master2 = Master(
        telegram_id=222222222,
        name="Master 2",
        phone="+79992222222",
        city="Москва",
        timezone="Europe/Moscow",
        is_onboarded=True,
        referral_code="MASTER2",
    )
    db_session.add(master2)
    
    await db_session.commit()
    await db_session.refresh(master1)
    await db_session.refresh(master2)
    
    # Create expense for master1
    await repo.create(
        master_id=master1.id,
        category="Supplies",
        amount=1000,
        expense_date=datetime.now(),
    )
    
    # Create expense for master2
    await repo.create(
        master_id=master2.id,
        category="Rent",
        amount=20000,
        expense_date=datetime.now(),
    )
    
    # Check isolation
    master1_expenses = await repo.get_by_master(master1.id)
    master2_expenses = await repo.get_by_master(master2.id)
    
    assert len(master1_expenses) == 1
    assert len(master2_expenses) == 1
    assert master1_expenses[0].category == "Supplies"
    assert master2_expenses[0].category == "Rent"

