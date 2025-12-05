"""Unit tests for AppointmentRepository."""
import pytest
from datetime import datetime, timedelta

from database.repositories.appointment import AppointmentRepository
from database.models import Appointment, AppointmentStatus, Master, Client, Service


@pytest.mark.asyncio
async def test_create_appointment(db_session, sample_master, sample_client, sample_service):
    """Test creating a new appointment."""
    repo = AppointmentRepository(db_session)
    
    start_time = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=1)
    
    appointment = await repo.create(
        master_id=sample_master.id,
        client_id=sample_client.id,
        service_id=sample_service.id,
        start_time=start_time,
        end_time=end_time,
        comment="Test comment"
    )
    
    assert appointment.id is not None
    assert appointment.master_id == sample_master.id
    assert appointment.client_id == sample_client.id
    assert appointment.service_id == sample_service.id
    assert appointment.status == AppointmentStatus.SCHEDULED.value
    assert appointment.comment == "Test comment"


@pytest.mark.asyncio
async def test_get_by_id(db_session, sample_master, sample_client, sample_service):
    """Test retrieving appointment by ID."""
    repo = AppointmentRepository(db_session)
    
    start_time = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=1)
    
    created = await repo.create(
        master_id=sample_master.id,
        client_id=sample_client.id,
        service_id=sample_service.id,
        start_time=start_time,
        end_time=end_time,
    )
    
    retrieved = await repo.get_by_id(created.id)
    
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.master_id == sample_master.id


@pytest.mark.asyncio
async def test_get_by_id_with_relations(db_session, sample_master, sample_client, sample_service):
    """Test retrieving appointment with related entities."""
    repo = AppointmentRepository(db_session)
    
    start_time = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=1)
    
    created = await repo.create(
        master_id=sample_master.id,
        client_id=sample_client.id,
        service_id=sample_service.id,
        start_time=start_time,
        end_time=end_time,
    )
    
    retrieved = await repo.get_by_id(created.id, with_relations=True)
    
    assert retrieved is not None
    assert retrieved.client.name == sample_client.name
    assert retrieved.service.name == sample_service.name


@pytest.mark.asyncio
async def test_get_by_master(db_session, sample_master, sample_client, sample_service):
    """Test retrieving appointments for a master."""
    repo = AppointmentRepository(db_session)
    
    # Create multiple appointments
    now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    
    await repo.create(
        master_id=sample_master.id,
        client_id=sample_client.id,
        service_id=sample_service.id,
        start_time=now,
        end_time=now + timedelta(hours=1),
    )
    
    await repo.create(
        master_id=sample_master.id,
        client_id=sample_client.id,
        service_id=sample_service.id,
        start_time=now + timedelta(days=1),
        end_time=now + timedelta(days=1, hours=1),
    )
    
    appointments = await repo.get_by_master(sample_master.id)
    
    assert len(appointments) == 2
    assert all(a.master_id == sample_master.id for a in appointments)


@pytest.mark.asyncio
async def test_get_by_master_with_date_filter(db_session, sample_master, sample_client, sample_service):
    """Test retrieving appointments with date filters."""
    repo = AppointmentRepository(db_session)
    
    now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    
    # Create appointments in different time periods
    await repo.create(
        master_id=sample_master.id,
        client_id=sample_client.id,
        service_id=sample_service.id,
        start_time=now,
        end_time=now + timedelta(hours=1),
    )
    
    await repo.create(
        master_id=sample_master.id,
        client_id=sample_client.id,
        service_id=sample_service.id,
        start_time=now + timedelta(days=10),
        end_time=now + timedelta(days=10, hours=1),
    )
    
    # Query with date range
    appointments = await repo.get_by_master(
        sample_master.id,
        start_date=now - timedelta(days=1),
        end_date=now + timedelta(days=5)
    )
    
    assert len(appointments) == 1


@pytest.mark.asyncio
async def test_get_by_master_with_status_filter(db_session, sample_master, sample_client, sample_service):
    """Test retrieving appointments with status filter."""
    repo = AppointmentRepository(db_session)
    
    now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    
    # Create appointments with different statuses
    app1 = await repo.create(
        master_id=sample_master.id,
        client_id=sample_client.id,
        service_id=sample_service.id,
        start_time=now,
        end_time=now + timedelta(hours=1),
    )
    
    app2 = await repo.create(
        master_id=sample_master.id,
        client_id=sample_client.id,
        service_id=sample_service.id,
        start_time=now + timedelta(days=1),
        end_time=now + timedelta(days=1, hours=1),
    )
    
    # Update one to completed
    await repo.update_status(app2.id, AppointmentStatus.COMPLETED)
    
    # Query only scheduled
    scheduled = await repo.get_by_master(
        sample_master.id,
        status=AppointmentStatus.SCHEDULED
    )
    
    assert len(scheduled) == 1
    assert scheduled[0].id == app1.id


@pytest.mark.asyncio
async def test_check_time_conflict_no_conflict(db_session, sample_master, sample_client, sample_service):
    """Test time conflict check with no conflicts."""
    repo = AppointmentRepository(db_session)
    
    now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    
    # Create existing appointment 10:00-11:00
    await repo.create(
        master_id=sample_master.id,
        client_id=sample_client.id,
        service_id=sample_service.id,
        start_time=now,
        end_time=now + timedelta(hours=1),
    )
    
    # Check for appointment 11:00-12:00 (no conflict)
    has_conflict = await repo.check_time_conflict(
        master_id=sample_master.id,
        start_time=now + timedelta(hours=1),
        end_time=now + timedelta(hours=2),
    )
    
    assert not has_conflict


@pytest.mark.asyncio
async def test_check_time_conflict_overlap_start(db_session, sample_master, sample_client, sample_service):
    """Test time conflict when new appointment overlaps start of existing."""
    repo = AppointmentRepository(db_session)
    
    now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    
    # Create existing appointment 10:00-11:00
    await repo.create(
        master_id=sample_master.id,
        client_id=sample_client.id,
        service_id=sample_service.id,
        start_time=now,
        end_time=now + timedelta(hours=1),
    )
    
    # Check for appointment 09:30-10:30 (overlaps start)
    has_conflict = await repo.check_time_conflict(
        master_id=sample_master.id,
        start_time=now - timedelta(minutes=30),
        end_time=now + timedelta(minutes=30),
    )
    
    assert has_conflict


@pytest.mark.asyncio
async def test_check_time_conflict_overlap_end(db_session, sample_master, sample_client, sample_service):
    """Test time conflict when new appointment overlaps end of existing."""
    repo = AppointmentRepository(db_session)
    
    now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    
    # Create existing appointment 10:00-11:00
    await repo.create(
        master_id=sample_master.id,
        client_id=sample_client.id,
        service_id=sample_service.id,
        start_time=now,
        end_time=now + timedelta(hours=1),
    )
    
    # Check for appointment 10:30-11:30 (overlaps end)
    has_conflict = await repo.check_time_conflict(
        master_id=sample_master.id,
        start_time=now + timedelta(minutes=30),
        end_time=now + timedelta(hours=1, minutes=30),
    )
    
    assert has_conflict


@pytest.mark.asyncio
async def test_check_time_conflict_contains(db_session, sample_master, sample_client, sample_service):
    """Test time conflict when new appointment contains existing."""
    repo = AppointmentRepository(db_session)
    
    now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    
    # Create existing appointment 10:00-11:00
    await repo.create(
        master_id=sample_master.id,
        client_id=sample_client.id,
        service_id=sample_service.id,
        start_time=now,
        end_time=now + timedelta(hours=1),
    )
    
    # Check for appointment 09:00-12:00 (contains existing)
    has_conflict = await repo.check_time_conflict(
        master_id=sample_master.id,
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(hours=2),
    )
    
    assert has_conflict


@pytest.mark.asyncio
async def test_check_time_conflict_ignore_cancelled(db_session, sample_master, sample_client, sample_service):
    """Test that cancelled appointments don't cause conflicts."""
    repo = AppointmentRepository(db_session)
    
    now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    
    # Create appointment and cancel it
    app = await repo.create(
        master_id=sample_master.id,
        client_id=sample_client.id,
        service_id=sample_service.id,
        start_time=now,
        end_time=now + timedelta(hours=1),
    )
    
    await repo.update_status(app.id, AppointmentStatus.CANCELLED)
    
    # Check for same time (should not conflict)
    has_conflict = await repo.check_time_conflict(
        master_id=sample_master.id,
        start_time=now,
        end_time=now + timedelta(hours=1),
    )
    
    assert not has_conflict


@pytest.mark.asyncio
async def test_update_status(db_session, sample_master, sample_client, sample_service):
    """Test updating appointment status."""
    repo = AppointmentRepository(db_session)
    
    now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    
    appointment = await repo.create(
        master_id=sample_master.id,
        client_id=sample_client.id,
        service_id=sample_service.id,
        start_time=now,
        end_time=now + timedelta(hours=1),
    )
    
    updated = await repo.update_status(
        appointment.id,
        AppointmentStatus.CONFIRMED,
    )
    
    assert updated.status == AppointmentStatus.CONFIRMED.value


@pytest.mark.asyncio
async def test_update_status_with_cancellation_reason(db_session, sample_master, sample_client, sample_service):
    """Test updating status with cancellation reason."""
    repo = AppointmentRepository(db_session)
    
    now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    
    appointment = await repo.create(
        master_id=sample_master.id,
        client_id=sample_client.id,
        service_id=sample_service.id,
        start_time=now,
        end_time=now + timedelta(hours=1),
    )
    
    updated = await repo.update_status(
        appointment.id,
        AppointmentStatus.CANCELLED,
        cancellation_reason="Client request"
    )
    
    assert updated.status == AppointmentStatus.CANCELLED.value
    assert updated.cancellation_reason == "Client request"


@pytest.mark.asyncio
async def test_update_appointment(db_session, sample_master, sample_client, sample_service):
    """Test generic appointment update."""
    repo = AppointmentRepository(db_session)
    
    now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    
    appointment = await repo.create(
        master_id=sample_master.id,
        client_id=sample_client.id,
        service_id=sample_service.id,
        start_time=now,
        end_time=now + timedelta(hours=1),
    )
    
    appointment.comment = "Updated comment"
    appointment.is_completed = True
    
    updated = await repo.update(appointment)
    
    assert updated.comment == "Updated comment"
    assert updated.is_completed is True
