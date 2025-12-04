"""Test reminder creation and sending."""
import asyncio
from datetime import datetime, timedelta, timezone

from database import async_session_maker, init_db
from database.repositories import MasterRepository, ServiceRepository, ClientRepository, AppointmentRepository, ReminderRepository
from database.models import ReminderStatus, ReminderType
from services.scheduler import create_appointment_reminders


async def test_reminders():
    """Test reminder creation for an appointment."""
    await init_db()
    
    async with async_session_maker() as session:
        # Get first master
        mrepo = MasterRepository(session)
        masters = await mrepo.get_all()
        
        if not masters:
            print("❌ No masters found. Create a master first by running /start in the bot.")
            return
        
        master = masters[0]
        print(f"✅ Testing with master: {master.name} (ID: {master.id})")
        
        # Get first service
        srepo = ServiceRepository(session)
        services = await srepo.get_all_by_master(master.id, active_only=True)
        
        if not services:
            print("❌ No services found")
            return
        
        service = services[0]
        print(f"✅ Using service: {service.name}")
        
        # Get or create a test client
        crepo = ClientRepository(session)
        client = await crepo.get_by_phone(master.id, "+79991234567")
        
        if not client:
            client = await crepo.create(
                master_id=master.id,
                name="Тестовый Клиент",
                phone="+79991234567",
                telegram_id=master.telegram_id  # Use master's telegram for testing
            )
            print(f"✅ Created test client: {client.name}")
        else:
            print(f"✅ Using existing client: {client.name}")
        
        # Create appointment 2 hours from now (so T-2h reminder will be due soon)
        arepo = AppointmentRepository(session)
        start_time = datetime.now(timezone.utc) + timedelta(hours=2, minutes=5)
        end_time = start_time + timedelta(minutes=service.duration_minutes)
        
        appointment = await arepo.create(
            master_id=master.id,
            client_id=client.id,
            service_id=service.id,
            start_time=start_time,
            end_time=end_time
        )
        await session.flush()
        print(f"✅ Created test appointment (ID: {appointment.id}) at {start_time}")
        
        # Create reminders
        reminder_count = await create_appointment_reminders(session, appointment, cancel_existing=False)
        await session.commit()
        print(f"✅ Created {reminder_count} reminders")
        
        # Check reminders
        rrepo = ReminderRepository(session)
        reminders = await rrepo.get_by_appointment(appointment.id)
        
        print(f"\n📋 Reminders for appointment {appointment.id}:")
        for reminder in reminders:
            time_diff = reminder.scheduled_time - datetime.now(timezone.utc)
            hours = time_diff.total_seconds() / 3600
            print(f"  - {reminder.reminder_type}: scheduled at {reminder.scheduled_time} ({hours:.1f}h from now)")
        
        # Check if any reminders are due now (for manual testing)
        now = datetime.now(timezone.utc)
        due_reminders = await rrepo.get_due_reminders(before_time=now, limit=10)
        
        if due_reminders:
            print(f"\n⏰ Found {len(due_reminders)} due reminders:")
            for r in due_reminders:
                print(f"  - ID {r.id}: {r.reminder_type} for appointment {r.appointment_id}")
        else:
            print(f"\n⏰ No reminders due yet. Wait {hours:.1f} hours and check again.")
        
        print("\n✅ Test completed! Reminders will be sent automatically by the scheduler.")


if __name__ == "__main__":
    asyncio.run(test_reminders())
