"""Performance testing script for database queries."""
import asyncio
import os
import sys
import time
from datetime import datetime, timedelta
from typing import List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from bot.config import settings
from database.models import Appointment, AppointmentStatus, Client, Reminder, ReminderStatus


# Create async engine
engine = create_async_engine(str(settings.database_url), echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def measure_query(session: AsyncSession, query, description: str) -> float:
    """Measure query execution time."""
    start = time.time()
    result = await session.execute(query)
    result.all()  # Fetch all results
    elapsed = time.time() - start
    print(f"✓ {description}: {elapsed*1000:.2f}ms")
    return elapsed


async def test_appointment_queries(session: AsyncSession):
    """Test appointment-related queries."""
    print("\n📊 Testing Appointment Queries")
    print("=" * 60)
    
    # Test 1: Get master appointments with filters
    query1 = select(Appointment).where(
        and_(
            Appointment.master_id == 1,
            Appointment.start_time >= datetime.now(),
            Appointment.start_time <= datetime.now() + timedelta(days=7),
            Appointment.status.in_([
                AppointmentStatus.SCHEDULED.value,
                AppointmentStatus.CONFIRMED.value
            ])
        )
    ).order_by(Appointment.start_time)
    
    await measure_query(session, query1, "Get master appointments (7 days, filtered)")
    
    # Test 2: Time conflict check
    test_start = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    test_end = test_start + timedelta(hours=1)
    
    query2 = select(Appointment).where(
        and_(
            Appointment.master_id == 1,
            Appointment.status.in_([
                AppointmentStatus.SCHEDULED.value,
                AppointmentStatus.CONFIRMED.value
            ]),
            or_(
                and_(
                    Appointment.start_time <= test_start,
                    Appointment.end_time > test_start
                ),
                and_(
                    Appointment.start_time < test_end,
                    Appointment.end_time >= test_end
                ),
                and_(
                    Appointment.start_time >= test_start,
                    Appointment.end_time <= test_end
                )
            )
        )
    ).limit(1)
    
    await measure_query(session, query2, "Check time conflict")
    
    # Test 3: Get client appointments
    query3 = select(Appointment).where(
        and_(
            Appointment.client_id == 1,
            Appointment.status.in_([
                AppointmentStatus.SCHEDULED.value,
                AppointmentStatus.CONFIRMED.value
            ])
        )
    ).order_by(Appointment.start_time.desc())
    
    await measure_query(session, query3, "Get client appointments")
    
    # Test 4: Get appointments by status (for stats)
    query4 = select(Appointment).where(
        and_(
            Appointment.master_id == 1,
            Appointment.status == AppointmentStatus.COMPLETED.value,
            Appointment.start_time >= datetime.now() - timedelta(days=30)
        )
    )
    
    await measure_query(session, query4, "Get completed appointments (30 days)")


async def test_reminder_queries(session: AsyncSession):
    """Test reminder-related queries."""
    print("\n📬 Testing Reminder Queries")
    print("=" * 60)
    
    # Test 1: Get scheduled reminders to send
    query1 = select(Reminder).where(
        and_(
            Reminder.status == ReminderStatus.SCHEDULED.value,
            Reminder.scheduled_time <= datetime.now()
        )
    ).order_by(Reminder.scheduled_time).limit(100)
    
    await measure_query(session, query1, "Get scheduled reminders to send")


async def test_client_queries(session: AsyncSession):
    """Test client-related queries."""
    print("\n👤 Testing Client Queries")
    print("=" * 60)
    
    # Test 1: Find client by telegram_id
    query1 = select(Client).where(
        and_(
            Client.master_id == 1,
            Client.telegram_id == 123456789
        )
    )
    
    await measure_query(session, query1, "Find client by telegram_id")
    
    # Test 2: Find client by phone
    query2 = select(Client).where(
        and_(
            Client.master_id == 1,
            Client.phone == "+79999999999"
        )
    )
    
    await measure_query(session, query2, "Find client by phone")


async def test_index_usage(session: AsyncSession):
    """Check if indexes are being used."""
    print("\n📈 Checking Index Usage")
    print("=" * 60)
    
    # Get index usage stats
    query = text("""
        SELECT
            schemaname,
            relname as tablename,
            indexrelname as indexname,
            idx_scan as scans,
            pg_size_pretty(pg_relation_size(indexrelid)) as size
        FROM pg_stat_user_indexes
        WHERE schemaname = 'public'
          AND indexrelname LIKE 'ix_%'
        ORDER BY idx_scan DESC
        LIMIT 10
    """)
    
    result = await session.execute(query)
    rows = result.fetchall()
    
    print("\nTop 10 Most Used Indexes:")
    print(f"{'Table':<20} {'Index':<40} {'Scans':<10} {'Size':<10}")
    print("-" * 80)
    for row in rows:
        print(f"{row.tablename:<20} {row.indexname:<40} {row.scans:<10} {row.size:<10}")


async def test_table_stats(session: AsyncSession):
    """Check table statistics."""
    print("\n📊 Table Statistics")
    print("=" * 60)
    
    query = text("""
        SELECT
            schemaname,
            relname as tablename,
            n_live_tup as live_rows,
            n_dead_tup as dead_rows,
            pg_size_pretty(pg_total_relation_size(schemaname||'.'||relname)) as total_size
        FROM pg_stat_user_tables
        WHERE schemaname = 'public'
        ORDER BY n_live_tup DESC
    """)
    
    result = await session.execute(query)
    rows = result.fetchall()
    
    print(f"\n{'Table':<20} {'Live Rows':<12} {'Dead Rows':<12} {'Total Size':<12}")
    print("-" * 60)
    for row in rows:
        print(f"{row.tablename:<20} {row.live_rows:<12} {row.dead_rows:<12} {row.total_size:<12}")


async def main():
    """Run all performance tests."""
    print("\n" + "=" * 60)
    print("🚀 BeautyAssist Database Performance Test")
    print("=" * 60)
    
    async with async_session() as session:
        try:
            # Test queries
            await test_appointment_queries(session)
            await test_reminder_queries(session)
            await test_client_queries(session)
            
            # Check stats
            await test_index_usage(session)
            await test_table_stats(session)
            
            print("\n" + "=" * 60)
            print("✅ Performance tests completed!")
            print("=" * 60)
            
        except Exception as e:
            print(f"\n❌ Error during testing: {e}")
            raise
        finally:
            await session.close()


if __name__ == "__main__":
    asyncio.run(main())
