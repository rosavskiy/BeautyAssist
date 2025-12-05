"""Unit tests for ClientRepository."""
import pytest

from database.repositories.client import ClientRepository
from database.models import Client, Master


@pytest.mark.asyncio
async def test_create_client(db_session, sample_master):
    """Test creating a new client."""
    repo = ClientRepository(db_session)
    
    client = await repo.create(
        master_id=sample_master.id,
        telegram_id=111111111,
        telegram_username="new_client",
        name="New Client",
        phone="+79991111111",
        source="instagram"
    )
    
    assert client.id is not None
    assert client.master_id == sample_master.id
    assert client.telegram_id == 111111111
    assert client.name == "New Client"
    assert client.phone == "+79991111111"
    assert client.source == "instagram"


@pytest.mark.asyncio
async def test_get_by_id(db_session, sample_master, sample_client):
    """Test retrieving client by ID."""
    repo = ClientRepository(db_session)
    
    retrieved = await repo.get_by_id(sample_client.id)
    
    assert retrieved is not None
    assert retrieved.id == sample_client.id
    assert retrieved.name == sample_client.name


@pytest.mark.asyncio
async def test_get_by_telegram_id(db_session, sample_master, sample_client):
    """Test finding client by telegram_id and master_id."""
    repo = ClientRepository(db_session)
    
    retrieved = await repo.get_by_telegram_id(
        sample_master.id,
        sample_client.telegram_id
    )
    
    assert retrieved is not None
    assert retrieved.id == sample_client.id
    assert retrieved.telegram_id == sample_client.telegram_id


@pytest.mark.asyncio
async def test_get_by_telegram_id_not_found(db_session, sample_master):
    """Test that non-existent telegram_id returns None."""
    repo = ClientRepository(db_session)
    
    retrieved = await repo.get_by_telegram_id(
        sample_master.id,
        999999999  # Non-existent
    )
    
    assert retrieved is None


@pytest.mark.asyncio
async def test_get_by_phone(db_session, sample_master, sample_client):
    """Test finding client by phone number."""
    repo = ClientRepository(db_session)
    
    retrieved = await repo.get_by_phone(
        sample_master.id,
        sample_client.phone
    )
    
    assert retrieved is not None
    assert retrieved.id == sample_client.id
    assert retrieved.phone == sample_client.phone


@pytest.mark.asyncio
async def test_get_by_phone_not_found(db_session, sample_master):
    """Test that non-existent phone returns None."""
    repo = ClientRepository(db_session)
    
    retrieved = await repo.get_by_phone(
        sample_master.id,
        "+79999999999"  # Non-existent
    )
    
    assert retrieved is None


@pytest.mark.asyncio
async def test_get_all_by_master(db_session, sample_master):
    """Test retrieving all clients for a master."""
    repo = ClientRepository(db_session)
    
    # Create multiple clients
    await repo.create(
        master_id=sample_master.id,
        telegram_id=111111111,
        name="Client 1",
        phone="+79991111111",
    )
    
    await repo.create(
        master_id=sample_master.id,
        telegram_id=222222222,
        name="Client 2",
        phone="+79992222222",
    )
    
    clients = await repo.get_all_by_master(sample_master.id)
    
    assert len(clients) >= 2
    assert all(c.master_id == sample_master.id for c in clients)


@pytest.mark.asyncio
async def test_search_by_name(db_session, sample_master):
    """Test searching clients by name."""
    repo = ClientRepository(db_session)
    
    await repo.create(
        master_id=sample_master.id,
        telegram_id=111111111,
        name="Анна Иванова",
        phone="+79991111111",
    )
    
    await repo.create(
        master_id=sample_master.id,
        telegram_id=222222222,
        name="Мария Петрова",
        phone="+79992222222",
    )
    
    results = await repo.search_by_name(sample_master.id, "Анна")
    
    assert len(results) == 1
    assert "Анна" in results[0].name


@pytest.mark.asyncio
async def test_search_by_name_case_insensitive(db_session, sample_master):
    """Test that name search is case-insensitive."""
    repo = ClientRepository(db_session)
    
    await repo.create(
        master_id=sample_master.id,
        telegram_id=111111111,
        name="Анна Иванова",
        phone="+79991111111",
    )
    
    results = await repo.search_by_name(sample_master.id, "анна")
    
    assert len(results) == 1


@pytest.mark.asyncio
async def test_update_client(db_session, sample_master, sample_client):
    """Test updating client information."""
    repo = ClientRepository(db_session)
    
    sample_client.name = "Updated Name"
    sample_client.notes = "Important notes"
    
    updated = await repo.update(sample_client)
    
    assert updated.name == "Updated Name"
    assert updated.notes == "Important notes"


@pytest.mark.asyncio
async def test_count_clients(db_session, sample_master):
    """Test counting clients for a master."""
    repo = ClientRepository(db_session)
    
    # Create a few clients
    await repo.create(
        master_id=sample_master.id,
        telegram_id=111111111,
        name="Client 1",
        phone="+79991111111",
    )
    
    await repo.create(
        master_id=sample_master.id,
        telegram_id=222222222,
        name="Client 2",
        phone="+79992222222",
    )
    
    count = await repo.count_by_master(sample_master.id)
    
    assert count >= 2


@pytest.mark.asyncio
async def test_client_isolation_between_masters(db_session):
    """Test that clients are properly isolated between masters."""
    repo = ClientRepository(db_session)
    
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
    
    # Create client for master1
    client1 = await repo.create(
        master_id=master1.id,
        telegram_id=333333333,
        name="Client of Master 1",
        phone="+79993333333",
    )
    
    # Try to find this client from master2's perspective
    found = await repo.get_by_telegram_id(master2.id, 333333333)
    
    assert found is None  # Should not find client from another master
    
    # But master1 should find it
    found = await repo.get_by_telegram_id(master1.id, 333333333)
    assert found is not None
    assert found.id == client1.id
