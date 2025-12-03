"""Client repository for database operations."""
from typing import Optional, List
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Client


class ClientRepository:
    """Repository for Client model operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, client_id: int) -> Optional[Client]:
        """Get client by ID."""
        result = await self.session.execute(
            select(Client).where(Client.id == client_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_phone(self, master_id: int, phone: str) -> Optional[Client]:
        """Get client by phone number for specific master."""
        result = await self.session.execute(
            select(Client).where(
                Client.master_id == master_id,
                Client.phone == phone
            )
        )
        return result.scalar_one_or_none()
    
    async def get_by_telegram_id(self, master_id: int, telegram_id: int) -> Optional[Client]:
        """Get client by Telegram ID for specific master."""
        result = await self.session.execute(
            select(Client).where(
                Client.master_id == master_id,
                Client.telegram_id == telegram_id
            )
        )
        return result.scalar_one_or_none()
    
    async def get_all_by_master(self, master_id: int, limit: int = 100) -> List[Client]:
        """Get all clients for master."""
        result = await self.session.execute(
            select(Client)
            .where(Client.master_id == master_id)
            .order_by(Client.name)
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def count_by_master(self, master_id: int) -> int:
        """Count total clients for master."""
        result = await self.session.execute(
            select(func.count(Client.id)).where(Client.master_id == master_id)
        )
        return result.scalar() or 0
    
    async def create(
        self,
        master_id: int,
        name: str,
        phone: str,
        telegram_id: Optional[int] = None,
        telegram_username: Optional[str] = None,
        source: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Client:
        """Create new client."""
        client = Client(
            master_id=master_id,
            name=name,
            phone=phone,
            telegram_id=telegram_id,
            telegram_username=telegram_username,
            source=source,
            notes=notes,
        )
        
        self.session.add(client)
        await self.session.flush()
        return client
    
    async def update(self, client: Client) -> Client:
        """Update client."""
        await self.session.flush()
        return client
    
    async def update_visit_stats(
        self,
        client_id: int,
        amount_spent: int,
    ) -> None:
        """Update client's visit statistics."""
        client = await self.get_by_id(client_id)
        if client:
            client.last_visit = datetime.utcnow()
            client.total_visits += 1
            client.total_spent += amount_spent
            await self.session.flush()
    
    async def search_by_name(
        self,
        master_id: int,
        query: str,
        limit: int = 20
    ) -> List[Client]:
        """Search clients by name."""
        result = await self.session.execute(
            select(Client)
            .where(
                Client.master_id == master_id,
                Client.name.ilike(f"%{query}%")
            )
            .order_by(Client.name)
            .limit(limit)
        )
        return list(result.scalars().all())
