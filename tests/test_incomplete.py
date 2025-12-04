"""Test incomplete appointments checker."""
import asyncio
from datetime import datetime, timedelta, timezone

from database import async_session_maker, init_db
from database.repositories import MasterRepository, ServiceRepository, ClientRepository, AppointmentRepository
from services.incomplete_checker import notify_masters_incomplete_appointments


async def test_incomplete_checker():
    """Test incomplete appointments notification."""
    await init_db()
    
    # Mock bot for testing (prints instead of sending)
    class MockBot:
        async def send_message(self, chat_id, text, parse_mode=None, reply_markup=None):
            print(f"\n📨 Message to {chat_id}:")
            print(text)
            if reply_markup:
                print(f"Buttons: {len(reply_markup.inline_keyboard)} rows")
    
    mock_bot = MockBot()
    
    async with async_session_maker() as session:
        # Get first master
        mrepo = MasterRepository(session)
        masters = await mrepo.get_all()
        
        if not masters:
            print("❌ No masters found. Create a master first.")
            return
        
        master = masters[0]
        print(f"✅ Testing with master: {master.name} (ID: {master.id})")
        
        # Get incomplete appointments
        arepo = AppointmentRepository(session)
        incomplete = await arepo.get_past_incomplete(master_id=master.id)
        
        print(f"\n📋 Found {len(incomplete)} incomplete appointments")
        
        if incomplete:
            for app in incomplete[:5]:  # Show first 5
                print(f"  - ID {app.id}: {app.start_time} - {app.service.name if app.service else 'Service'}")
        else:
            # Create a test incomplete appointment (in the past)
            srepo = ServiceRepository(session)
            crepo = ClientRepository(session)
            
            services = await srepo.get_all_by_master(master.id, active_only=True)
            if not services:
                print("❌ No services found")
                return
            
            service = services[0]
            
            # Get or create test client
            client = await crepo.get_by_phone(master.id, "+79991234567")
            if not client:
                client = await crepo.create(
                    master_id=master.id,
                    name="Тестовый Клиент",
                    phone="+79991234567"
                )
            
            # Create appointment 2 hours ago (past, incomplete)
            past_time = datetime.now(timezone.utc) - timedelta(hours=2)
            end_time = past_time + timedelta(minutes=service.duration_minutes)
            
            app = await arepo.create(
                master_id=master.id,
                client_id=client.id,
                service_id=service.id,
                start_time=past_time,
                end_time=end_time
            )
            await session.commit()
            print(f"\n✅ Created test incomplete appointment (ID: {app.id})")
            
            incomplete = [app]
        
        # Test notification
        print("\n🔔 Sending notification...")
        notified = await notify_masters_incomplete_appointments(mock_bot, session)
        print(f"\n✅ Notified {notified} masters")


if __name__ == "__main__":
    asyncio.run(test_incomplete_checker())
