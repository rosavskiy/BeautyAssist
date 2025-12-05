import sys
import os
import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

# Ensure project root is on sys.path so `import bot` works
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from database.base import Base
from database.models import Master, Client, Service, Appointment, Reminder
from bot.config import settings


# Test database URL (use separate test database)
TEST_DATABASE_URL = str(settings.database_url).replace('/beautyassist', '/beautyassist_test')


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create async engine for tests."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,  # Disable pooling for tests
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for tests."""
    async_session = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def sample_master(db_session: AsyncSession) -> Master:
    """Create sample master for tests."""
    master = Master(
        telegram_id=123456789,
        telegram_username="test_master",
        name="Test Master",
        phone="+79991234567",
        city="Москва",
        timezone="Europe/Moscow",
        is_onboarded=True,
        referral_code="TEST123",
    )
    db_session.add(master)
    await db_session.commit()
    await db_session.refresh(master)
    return master


@pytest_asyncio.fixture
async def sample_client(db_session: AsyncSession, sample_master: Master) -> Client:
    """Create sample client for tests."""
    client = Client(
        master_id=sample_master.id,
        telegram_id=987654321,
        telegram_username="test_client",
        name="Test Client",
        phone="+79997654321",
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


@pytest_asyncio.fixture
async def sample_service(db_session: AsyncSession, sample_master: Master) -> Service:
    """Create sample service for tests."""
    service = Service(
        master_id=sample_master.id,
        name="Test Service",
        duration_minutes=60,
        price=1000,
        is_active=True,
    )
    db_session.add(service)
    await db_session.commit()
    await db_session.refresh(service)
    return service
