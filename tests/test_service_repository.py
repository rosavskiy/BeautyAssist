"""Unit tests for ServiceRepository."""
import pytest

from database.repositories.service import ServiceRepository
from database.models import Service


@pytest.mark.asyncio
async def test_create_service(db_session, sample_master):
    """Test creating a new service."""
    repo = ServiceRepository(db_session)
    
    service = await repo.create(
        master_id=sample_master.id,
        name="Haircut",
        duration_minutes=60,
        price=1500,
        description="Professional haircut"
    )
    
    assert service.id is not None
    assert service.master_id == sample_master.id
    assert service.name == "Haircut"
    assert service.duration_minutes == 60
    assert service.price == 1500
    assert service.description == "Professional haircut"
    assert service.is_active is True


@pytest.mark.asyncio
async def test_get_by_id(db_session, sample_service):
    """Test retrieving service by ID."""
    repo = ServiceRepository(db_session)
    
    retrieved = await repo.get_by_id(sample_service.id)
    
    assert retrieved is not None
    assert retrieved.id == sample_service.id
    assert retrieved.name == sample_service.name


@pytest.mark.asyncio
async def test_get_all_by_master(db_session, sample_master):
    """Test retrieving all services for a master."""
    repo = ServiceRepository(db_session)
    
    # Create multiple services
    await repo.create(
        master_id=sample_master.id,
        name="Service 1",
        duration_minutes=30,
        price=500,
    )
    
    await repo.create(
        master_id=sample_master.id,
        name="Service 2",
        duration_minutes=60,
        price=1000,
    )
    
    services = await repo.get_all_by_master(sample_master.id)
    
    assert len(services) >= 2
    assert all(s.master_id == sample_master.id for s in services)


@pytest.mark.asyncio
async def test_get_all_by_master_active_only(db_session, sample_master):
    """Test retrieving only active services."""
    repo = ServiceRepository(db_session)
    
    # Create active service
    active = await repo.create(
        master_id=sample_master.id,
        name="Active Service",
        duration_minutes=30,
        price=500,
    )
    
    # Create inactive service
    inactive = await repo.create(
        master_id=sample_master.id,
        name="Inactive Service",
        duration_minutes=60,
        price=1000,
    )
    inactive.is_active = False
    await repo.update(inactive)
    
    # Get only active
    services = await repo.get_all_by_master(sample_master.id, active_only=True)
    
    assert len(services) >= 1
    assert all(s.is_active for s in services)
    assert any(s.id == active.id for s in services)
    assert not any(s.id == inactive.id for s in services)


@pytest.mark.asyncio
async def test_update_service(db_session, sample_service):
    """Test updating service information."""
    repo = ServiceRepository(db_session)
    
    sample_service.name = "Updated Service Name"
    sample_service.price = 2000
    sample_service.duration = 90
    
    updated = await repo.update(sample_service)
    
    assert updated.name == "Updated Service Name"
    assert updated.price == 2000
    assert updated.duration == 90


@pytest.mark.asyncio
async def test_deactivate_service(db_session, sample_service):
    """Test deactivating a service."""
    repo = ServiceRepository(db_session)
    
    sample_service.is_active = False
    updated = await repo.update(sample_service)
    
    assert updated.is_active is False


@pytest.mark.asyncio
async def test_count_services(db_session, sample_master):
    """Test counting services for a master."""
    repo = ServiceRepository(db_session)
    
    # Create services
    await repo.create(
        master_id=sample_master.id,
        name="Service 1",
        duration_minutes=30,
        price=500,
    )
    
    await repo.create(
        master_id=sample_master.id,
        name="Service 2",
        duration_minutes=60,
        price=1000,
    )
    
    count = await repo.count_by_master(sample_master.id)
    
    assert count >= 2


@pytest.mark.asyncio
async def test_count_active_services(db_session, sample_master):
    """Test counting only active services."""
    repo = ServiceRepository(db_session)
    
    # Create active service
    await repo.create(
        master_id=sample_master.id,
        name="Active",
        duration_minutes=30,
        price=500,
    )
    
    # Create inactive service
    inactive = await repo.create(
        master_id=sample_master.id,
        name="Inactive",
        duration_minutes=60,
        price=1000,
    )
    inactive.is_active = False
    await repo.update(inactive)
    
    count = await repo.count_by_master(sample_master.id, active_only=True)
    
    assert count >= 1


@pytest.mark.asyncio
async def test_service_ordering(db_session, sample_master):
    """Test that services are ordered by name."""
    repo = ServiceRepository(db_session)
    
    # Create services in non-alphabetical order
    await repo.create(
        master_id=sample_master.id,
        name="Zebra Service",
        duration_minutes=30,
        price=500,
    )
    
    await repo.create(
        master_id=sample_master.id,
        name="Alpha Service",
        duration_minutes=60,
        price=1000,
    )
    
    await repo.create(
        master_id=sample_master.id,
        name="Beta Service",
        duration_minutes=45,
        price=750,
    )
    
    services = await repo.get_all_by_master(sample_master.id)
    
    # Check ordering
    names = [s.name for s in services]
    assert names == sorted(names)


@pytest.mark.asyncio
async def test_service_isolation_between_masters(db_session):
    """Test that services are properly isolated between masters."""
    from database.models import Master
    
    repo = ServiceRepository(db_session)
    
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
    
    # Create services for each master
    await repo.create(
        master_id=master1.id,
        name="Master 1 Service",
        duration_minutes=30,
        price=500,
    )
    
    await repo.create(
        master_id=master2.id,
        name="Master 2 Service",
        duration_minutes=60,
        price=1000,
    )
    
    # Check isolation
    master1_services = await repo.get_all_by_master(master1.id)
    master2_services = await repo.get_all_by_master(master2.id)
    
    assert len(master1_services) == 1
    assert len(master2_services) == 1
    assert master1_services[0].name == "Master 1 Service"
    assert master2_services[0].name == "Master 2 Service"
