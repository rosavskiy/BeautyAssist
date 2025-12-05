"""Unit tests for ReminderRepository."""
import pytest
from datetime import datetime, timedelta

from database.repositories.reminder import ReminderRepository
from database.models import Reminder, ReminderStatus, ReminderType, ReminderChannel


@pytest.mark.asyncio
async def test_create_reminder(db_session, sample_master, sample_client, sample_service):
    """Test creating a new reminder."""
    from database.repositories.appointment import AppointmentRepository
    
    # Create appointment first
    app_repo = AppointmentRepository(db_session)
    appointment = await app_repo.create(
        master_id=sample_master.id,
        client_id=sample_client.id,
        service_id=sample_service.id,
        start_time=datetime.now() + timedelta(days=1),
        end_time=datetime.now() + timedelta(days=1, hours=1),
    )
    
    repo = ReminderRepository(db_session)
    
    reminder = await repo.create(
        appointment_id=appointment.id,
        reminder_type=ReminderType.T_MINUS_24H,
        scheduled_time=datetime.now() + timedelta(hours=1),
    )
    
    assert reminder.id is not None
    assert reminder.appointment_id == appointment.id
    assert reminder.reminder_type == ReminderType.T_MINUS_24H.value
    assert reminder.status == ReminderStatus.SCHEDULED.value
    assert reminder.channel == ReminderChannel.TELEGRAM.value


@pytest.mark.asyncio
async def test_get_by_id(db_session, sample_master, sample_client, sample_service):
    """Test retrieving reminder by ID."""
    from database.repositories.appointment import AppointmentRepository
    
    app_repo = AppointmentRepository(db_session)
    appointment = await app_repo.create(
        master_id=sample_master.id,
        client_id=sample_client.id,
        service_id=sample_service.id,
        start_time=datetime.now() + timedelta(days=1),
        end_time=datetime.now() + timedelta(days=1, hours=1),
    )
    
    repo = ReminderRepository(db_session)
    created = await repo.create(
        appointment_id=appointment.id,
        reminder_type=ReminderType.T_MINUS_2H,
        scheduled_time=datetime.now() + timedelta(hours=1),
    )
    
    retrieved = await repo.get_by_id(created.id)
    
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.reminder_type == ReminderType.T_MINUS_2H.value


@pytest.mark.asyncio
async def test_get_pending_reminders(db_session, sample_master, sample_client, sample_service):
    """Test retrieving pending reminders to send."""
    from database.repositories.appointment import AppointmentRepository
    
    app_repo = AppointmentRepository(db_session)
    appointment = await app_repo.create(
        master_id=sample_master.id,
        client_id=sample_client.id,
        service_id=sample_service.id,
        start_time=datetime.now() + timedelta(days=1),
        end_time=datetime.now() + timedelta(days=1, hours=1),
    )
    
    repo = ReminderRepository(db_session)
    
    # Create reminder scheduled for past (should be returned)
    past_reminder = await repo.create(
        appointment_id=appointment.id,
        reminder_type=ReminderType.T_MINUS_24H,
        scheduled_time=datetime.now() - timedelta(hours=1),
    )
    
    # Create reminder scheduled for future (should not be returned)
    await repo.create(
        appointment_id=appointment.id,
        reminder_type=ReminderType.T_MINUS_2H,
        scheduled_time=datetime.now() + timedelta(hours=1),
    )
    
    pending = await repo.get_due_reminders(datetime.now())
    
    assert len(pending) == 1
    assert pending[0].id == past_reminder.id


@pytest.mark.asyncio
async def test_get_by_appointment(db_session, sample_master, sample_client, sample_service):
    """Test retrieving reminders for specific appointment."""
    from database.repositories.appointment import AppointmentRepository
    
    app_repo = AppointmentRepository(db_session)
    appointment = await app_repo.create(
        master_id=sample_master.id,
        client_id=sample_client.id,
        service_id=sample_service.id,
        start_time=datetime.now() + timedelta(days=1),
        end_time=datetime.now() + timedelta(days=1, hours=1),
    )
    
    repo = ReminderRepository(db_session)
    
    # Create multiple reminders
    await repo.create(
        appointment_id=appointment.id,
        reminder_type=ReminderType.T_MINUS_24H,
        scheduled_time=datetime.now() + timedelta(hours=1),
    )
    
    await repo.create(
        appointment_id=appointment.id,
        reminder_type=ReminderType.T_MINUS_2H,
        scheduled_time=datetime.now() + timedelta(hours=2),
    )
    
    reminders = await repo.get_by_appointment(appointment.id)
    
    assert len(reminders) == 2
    assert all(r.appointment_id == appointment.id for r in reminders)


@pytest.mark.asyncio
async def test_get_by_appointment_with_status_filter(db_session, sample_master, sample_client, sample_service):
    """Test filtering reminders by status."""
    from database.repositories.appointment import AppointmentRepository
    
    app_repo = AppointmentRepository(db_session)
    appointment = await app_repo.create(
        master_id=sample_master.id,
        client_id=sample_client.id,
        service_id=sample_service.id,
        start_time=datetime.now() + timedelta(days=1),
        end_time=datetime.now() + timedelta(days=1, hours=1),
    )
    
    repo = ReminderRepository(db_session)
    
    # Create scheduled reminder
    scheduled = await repo.create(
        appointment_id=appointment.id,
        reminder_type=ReminderType.T_MINUS_24H,
        scheduled_time=datetime.now() + timedelta(hours=1),
    )
    
    # Create another scheduled reminder
    await repo.create(
        appointment_id=appointment.id,
        reminder_type=ReminderType.T_MINUS_2H,
        scheduled_time=datetime.now() + timedelta(hours=2),
    )
    
    # Get only scheduled
    scheduled_reminders = await repo.get_by_appointment(
        appointment.id,
        status=ReminderStatus.SCHEDULED
    )
    
    assert len(scheduled_reminders) == 2



