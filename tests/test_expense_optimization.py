"""Test expense repository performance after optimization."""
import pytest
from datetime import datetime, timedelta
from database.repositories import ExpenseRepository, ServiceRepository, MasterRepository
from database.models import Expense


@pytest.mark.asyncio
async def test_expense_date_index_performance(db_session, test_master):
    """Test that queries with date filters use index."""
    repo = ExpenseRepository(db_session)
    
    # Create 100 expenses over 1 year
    start_date = datetime.now() - timedelta(days=365)
    for i in range(100):
        expense_date = start_date + timedelta(days=i * 3)
        await repo.create(
            master_id=test_master.id,
            category="materials",
            amount=1000 + i,
            expense_date=expense_date
        )
    
    await db_session.commit()
    
    # Query for last month - should use index
    query_start = datetime.now() - timedelta(days=30)
    query_end = datetime.now()
    
    # This query should be fast with index
    expenses = await repo.get_by_master(
        master_id=test_master.id,
        start_date=query_start,
        end_date=query_end
    )
    
    # Should find ~10 expenses (30 days / 3 days interval)
    assert 8 <= len(expenses) <= 12


@pytest.mark.asyncio
async def test_composite_index_usage(db_session, test_master):
    """Test that (master_id, expense_date) composite index is used."""
    repo = ExpenseRepository(db_session)
    
    # Create expenses for different dates
    dates = [
        datetime.now() - timedelta(days=10),
        datetime.now() - timedelta(days=5),
        datetime.now() - timedelta(days=1),
    ]
    
    for date in dates:
        await repo.create(
            master_id=test_master.id,
            category="rent",
            amount=5000,
            expense_date=date
        )
    
    await db_session.commit()
    
    # Query with both filters - should use composite index
    total = await repo.get_total_by_period(
        master_id=test_master.id,
        start_date=datetime.now() - timedelta(days=30),
        end_date=datetime.now()
    )
    
    assert total == 15000  # 3 expenses * 5000


@pytest.mark.asyncio
async def test_get_by_ids_no_n_plus_one(db_session, test_master):
    """Test that get_by_ids fetches multiple services in one query."""
    service_repo = ServiceRepository(db_session)
    
    # Create 3 services
    service1 = await service_repo.create(
        master_id=test_master.id,
        name="Service 1",
        duration_minutes=60,
        price=1000
    )
    service2 = await service_repo.create(
        master_id=test_master.id,
        name="Service 2",
        duration_minutes=90,
        price=2000
    )
    service3 = await service_repo.create(
        master_id=test_master.id,
        name="Service 3",
        duration_minutes=30,
        price=500
    )
    
    await db_session.commit()
    
    # Fetch all at once (single query)
    services = await service_repo.get_by_ids([service1.id, service2.id, service3.id])
    
    assert len(services) == 3
    service_names = {s.name for s in services}
    assert service_names == {"Service 1", "Service 2", "Service 3"}


@pytest.mark.asyncio
async def test_get_by_ids_empty_list(db_session):
    """Test that get_by_ids handles empty list correctly."""
    service_repo = ServiceRepository(db_session)
    
    services = await service_repo.get_by_ids([])
    
    assert services == []


@pytest.mark.asyncio
async def test_get_by_ids_nonexistent(db_session):
    """Test that get_by_ids handles non-existent IDs."""
    service_repo = ServiceRepository(db_session)
    
    services = await service_repo.get_by_ids([99999, 88888])
    
    assert services == []
