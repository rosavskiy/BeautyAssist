"""Tests for AdminRepository."""
import pytest
from datetime import datetime, timedelta, timezone

from database.models import Master, Client, Appointment, Service, Expense, AdminBroadcast
from database.models.appointment import AppointmentStatus
from database.repositories.admin import AdminRepository


@pytest.fixture
async def sample_masters(db_session):
    """Create sample masters for testing."""
    masters = [
        Master(
            telegram_id=111111,
            telegram_username="master1",
            name="Master One",
            phone="+79991111111",
            city="Москва",
            timezone="Europe/Moscow",
            is_onboarded=True,
            referral_code="REF001",
        ),
        Master(
            telegram_id=222222,
            telegram_username="master2",
            name="Master Two",
            phone="+79992222222",
            city="Санкт-Петербург",
            timezone="Europe/Moscow",
            is_onboarded=True,
            is_premium=True,
            referral_code="REF002",
        ),
        Master(
            telegram_id=333333,
            telegram_username="master3",
            name="Master Three",
            phone="+79993333333",
            city="Казань",
            timezone="Europe/Moscow",
            is_onboarded=False,
            referral_code="REF003",
        ),
    ]
    for master in masters:
        db_session.add(master)
    await db_session.commit()
    for master in masters:
        await db_session.refresh(master)
    return masters


@pytest.fixture
async def sample_clients(db_session, sample_masters):
    """Create sample clients for testing."""
    clients = [
        Client(
            master_id=sample_masters[0].id,
            telegram_id=444444,
            name="Client One",
            phone="+79994444444",
        ),
        Client(
            master_id=sample_masters[0].id,
            telegram_id=555555,
            name="Client Two",
            phone="+79995555555",
        ),
        Client(
            master_id=sample_masters[1].id,
            telegram_id=666666,
            name="Client Three",
            phone="+79996666666",
        ),
    ]
    for client in clients:
        db_session.add(client)
    await db_session.commit()
    for client in clients:
        await db_session.refresh(client)
    return clients


@pytest.fixture
async def sample_services(db_session, sample_masters):
    """Create sample services for testing."""
    services = [
        Service(
            master_id=sample_masters[0].id,
            name="Haircut",
            duration_minutes=60,
            price=1000,
            is_active=True,
        ),
        Service(
            master_id=sample_masters[1].id,
            name="Manicure",
            duration_minutes=90,
            price=1500,
            is_active=True,
        ),
    ]
    for service in services:
        db_session.add(service)
    await db_session.commit()
    for service in services:
        await db_session.refresh(service)
    return services


@pytest.fixture
async def sample_appointments(db_session, sample_masters, sample_clients, sample_services):
    """Create sample appointments for testing."""
    now = datetime.utcnow()
    appointments = [
        # Completed with payment
        Appointment(
            master_id=sample_masters[0].id,
            client_id=sample_clients[0].id,
            service_id=sample_services[0].id,
            start_time=now - timedelta(days=5),
            end_time=now - timedelta(days=5, hours=-1),
            status=AppointmentStatus.COMPLETED,
            is_completed=True,
            payment_amount=1000,
        ),
        # Completed without payment
        Appointment(
            master_id=sample_masters[0].id,
            client_id=sample_clients[1].id,
            service_id=sample_services[0].id,
            start_time=now - timedelta(days=3),
            end_time=now - timedelta(days=3, hours=-1),
            status=AppointmentStatus.COMPLETED,
            is_completed=True,
            payment_amount=None,
        ),
        # Scheduled
        Appointment(
            master_id=sample_masters[1].id,
            client_id=sample_clients[2].id,
            service_id=sample_services[1].id,
            start_time=now + timedelta(days=2),
            end_time=now + timedelta(days=2, hours=1, minutes=30),
            status=AppointmentStatus.SCHEDULED,
            is_completed=False,
        ),
        # Cancelled
        Appointment(
            master_id=sample_masters[0].id,
            client_id=sample_clients[0].id,
            service_id=sample_services[0].id,
            start_time=now - timedelta(days=1),
            end_time=now - timedelta(days=1, hours=-1),
            status=AppointmentStatus.CANCELLED,
            cancellation_reason="Client cancelled",
        ),
    ]
    for appointment in appointments:
        db_session.add(appointment)
    await db_session.commit()
    for appointment in appointments:
        await db_session.refresh(appointment)
    return appointments


@pytest.fixture
async def sample_expenses(db_session, sample_masters):
    """Create sample expenses for testing."""
    now = datetime.now(timezone.utc)
    expenses = [
        Expense(
            master_id=sample_masters[0].id,
            amount=500,
            category="Materials",
            description="Hair products",
            expense_date=now,
        ),
        Expense(
            master_id=sample_masters[1].id,
            amount=300,
            category="Rent",
            description="Studio rent",
            expense_date=now,
        ),
    ]
    for expense in expenses:
        db_session.add(expense)
    await db_session.commit()
    for expense in expenses:
        await db_session.refresh(expense)
    return expenses


@pytest.mark.asyncio
async def test_get_dashboard_stats(db_session, sample_masters, sample_clients, sample_appointments, sample_expenses):
    """Test getting dashboard statistics."""
    admin_repo = AdminRepository(db_session)
    
    stats = await admin_repo.get_dashboard_stats()
    
    assert stats["total_masters"] == 3
    assert stats["active_masters"] >= 1  # At least one master with appointments
    assert stats["total_clients"] == 3
    assert stats["total_appointments"] == 4
    assert stats["completed_appointments"] == 2
    assert stats["total_revenue"] == 1000.0  # Only completed with payment
    assert stats["pending_revenue"] == 0.0  # Completed without payment_amount
    assert stats["total_expenses"] == 800.0
    assert stats["net_profit"] == 200.0


@pytest.mark.asyncio
async def test_get_masters_list_basic(db_session, sample_masters):
    """Test getting basic masters list."""
    admin_repo = AdminRepository(db_session)
    
    masters = await admin_repo.get_masters_list(limit=10, offset=0)
    
    assert len(masters) == 3
    assert all(isinstance(m, Master) for m in masters)


@pytest.mark.asyncio
async def test_get_masters_list_pagination(db_session, sample_masters):
    """Test masters list pagination."""
    admin_repo = AdminRepository(db_session)
    
    # First page
    page1 = await admin_repo.get_masters_list(limit=2, offset=0)
    assert len(page1) == 2
    
    # Second page
    page2 = await admin_repo.get_masters_list(limit=2, offset=2)
    assert len(page2) == 1
    
    # No overlap
    page1_ids = {m.id for m in page1}
    page2_ids = {m.id for m in page2}
    assert len(page1_ids & page2_ids) == 0


@pytest.mark.asyncio
async def test_get_masters_list_filter_premium(db_session, sample_masters):
    """Test filtering masters by premium status."""
    admin_repo = AdminRepository(db_session)
    
    premium_masters = await admin_repo.get_masters_list(filter_premium=True)
    
    assert len(premium_masters) == 1
    assert premium_masters[0].is_premium is True


@pytest.mark.asyncio
async def test_get_masters_list_filter_onboarded(db_session, sample_masters):
    """Test filtering masters by onboarding status."""
    admin_repo = AdminRepository(db_session)
    
    onboarded = await admin_repo.get_masters_list(filter_onboarded=True)
    not_onboarded = await admin_repo.get_masters_list(filter_onboarded=False)
    
    assert len(onboarded) == 2
    assert len(not_onboarded) == 1
    assert all(m.is_onboarded for m in onboarded)
    assert all(not m.is_onboarded for m in not_onboarded)


@pytest.mark.asyncio
async def test_get_masters_list_search(db_session, sample_masters):
    """Test searching masters by name/username/phone."""
    admin_repo = AdminRepository(db_session)
    
    # Search by name
    results = await admin_repo.get_masters_list(search_query="Master One")
    assert len(results) == 1
    assert results[0].name == "Master One"
    
    # Search by username
    results = await admin_repo.get_masters_list(search_query="master2")
    assert len(results) == 1
    assert results[0].telegram_username == "master2"
    
    # Search by phone
    results = await admin_repo.get_masters_list(search_query="+79993333333")
    assert len(results) == 1
    assert results[0].phone == "+79993333333"


@pytest.mark.asyncio
async def test_get_master_stats(db_session, sample_masters, sample_clients, sample_services, sample_appointments, sample_expenses):
    """Test getting detailed master statistics."""
    admin_repo = AdminRepository(db_session)
    
    master_id = sample_masters[0].id
    stats = await admin_repo.get_master_stats(master_id)
    
    assert stats["total_clients"] == 2
    assert stats["total_services"] == 1
    assert stats["total_appointments"] == 3  # 2 completed, 1 cancelled
    assert stats["completed_appointments"] == 2
    assert stats["cancelled_appointments"] == 1
    assert stats["total_revenue"] == 1000.0
    assert stats["total_expenses"] == 500.0
    assert stats["net_profit"] == 500.0


@pytest.mark.asyncio
async def test_create_broadcast(db_session):
    """Test creating broadcast record."""
    admin_repo = AdminRepository(db_session)
    
    broadcast = await admin_repo.create_broadcast(
        content="Test broadcast message",
        created_by=123456789,
        total_recipients=10,
        target_filter="all"
    )
    
    assert broadcast.id is not None
    assert broadcast.content == "Test broadcast message"
    assert broadcast.created_by == 123456789
    assert broadcast.total_recipients == 10
    assert broadcast.target_filter == "all"
    assert broadcast.sent_count == 0
    assert broadcast.failed_count == 0
    assert broadcast.is_completed is False


@pytest.mark.asyncio
async def test_update_broadcast_progress(db_session):
    """Test updating broadcast sending progress."""
    admin_repo = AdminRepository(db_session)
    
    # Create broadcast
    broadcast = await admin_repo.create_broadcast(
        content="Test",
        created_by=123,
        total_recipients=10,
    )
    
    # Update progress
    await admin_repo.update_broadcast_progress(
        broadcast_id=broadcast.id,
        sent_count=7,
        failed_count=3,
        is_completed=True
    )
    
    # Refresh and check
    await db_session.refresh(broadcast)
    assert broadcast.sent_count == 7
    assert broadcast.failed_count == 3
    assert broadcast.is_completed is True
    assert broadcast.started_at is not None
    assert broadcast.completed_at is not None


@pytest.mark.asyncio
async def test_get_recent_broadcasts(db_session):
    """Test getting recent broadcast history."""
    admin_repo = AdminRepository(db_session)
    
    # Create multiple broadcasts
    for i in range(5):
        await admin_repo.create_broadcast(
            content=f"Broadcast {i}",
            created_by=123,
            total_recipients=10
        )
    
    # Get recent
    broadcasts = await admin_repo.get_recent_broadcasts(limit=3)
    
    assert len(broadcasts) == 3
    # Should be ordered by created_at desc (newest first)
    assert broadcasts[0].content == "Broadcast 4"
    assert broadcasts[1].content == "Broadcast 3"
    assert broadcasts[2].content == "Broadcast 2"


@pytest.mark.asyncio
async def test_get_all_master_telegram_ids(db_session, sample_masters):
    """Test getting all master telegram IDs for broadcasting."""
    admin_repo = AdminRepository(db_session)
    
    # Get all masters
    all_ids = await admin_repo.get_all_master_telegram_ids(filter_onboarded=False)
    assert len(all_ids) == 3
    assert set(all_ids) == {111111, 222222, 333333}
    
    # Get only onboarded
    onboarded_ids = await admin_repo.get_all_master_telegram_ids(filter_onboarded=True)
    assert len(onboarded_ids) == 2
    assert set(onboarded_ids) == {111111, 222222}


@pytest.mark.asyncio
async def test_dashboard_empty_database(db_session):
    """Test dashboard stats with empty database."""
    admin_repo = AdminRepository(db_session)
    
    stats = await admin_repo.get_dashboard_stats()
    
    assert stats["total_masters"] == 0
    assert stats["active_masters"] == 0
    assert stats["total_clients"] == 0
    assert stats["total_appointments"] == 0
    assert stats["completed_appointments"] == 0
    assert stats["total_revenue"] == 0.0
    assert stats["pending_revenue"] == 0.0
    assert stats["total_expenses"] == 0.0
    assert stats["net_profit"] == 0.0


@pytest.mark.asyncio
async def test_master_stats_no_data(db_session, sample_masters):
    """Test master stats with no appointments/expenses."""
    admin_repo = AdminRepository(db_session)
    
    master_id = sample_masters[2].id  # Master with no data
    stats = await admin_repo.get_master_stats(master_id)
    
    assert stats["total_clients"] == 0
    assert stats["total_services"] == 0
    assert stats["total_appointments"] == 0
    assert stats["completed_appointments"] == 0
    assert stats["cancelled_appointments"] == 0
    assert stats["total_revenue"] == 0.0
    assert stats["total_expenses"] == 0.0
    assert stats["net_profit"] == 0.0
