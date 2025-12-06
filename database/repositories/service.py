"""Service repository for database operations."""
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Service


class ServiceRepository:
    """Repository for Service model operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, service_id: int) -> Optional[Service]:
        """Get service by ID."""
        result = await self.session.execute(
            select(Service).where(Service.id == service_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_ids(self, service_ids: List[int]) -> List[Service]:
        """Get multiple services by IDs (for prefetching)."""
        if not service_ids:
            return []
        
        result = await self.session.execute(
            select(Service).where(Service.id.in_(service_ids))
        )
        return list(result.scalars().all())
    
    async def get_all_by_master(
        self,
        master_id: int,
        active_only: bool = True
    ) -> List[Service]:
        """Get all services for master."""
        query = select(Service).where(Service.master_id == master_id)
        
        if active_only:
            query = query.where(Service.is_active == True)
        
        query = query.order_by(Service.name)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def count_by_master(self, master_id: int, active_only: bool = True) -> int:
        """Count services for master."""
        query = select(func.count(Service.id)).where(Service.master_id == master_id)
        
        if active_only:
            query = query.where(Service.is_active == True)
        
        result = await self.session.execute(query)
        return result.scalar() or 0
    
    async def create(
        self,
        master_id: int,
        name: str,
        duration_minutes: int,
        price: int,
        category: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Service:
        """Create new service."""
        service = Service(
            master_id=master_id,
            name=name,
            duration_minutes=duration_minutes,
            price=price,
            category=category,
            description=description,
            is_active=True,
        )
        
        self.session.add(service)
        await self.session.flush()
        return service
    
    async def update(self, service: Service) -> Service:
        """Update service."""
        await self.session.flush()
        return service
    
    async def deactivate(self, service_id: int) -> None:
        """Deactivate service."""
        service = await self.get_by_id(service_id)
        if service:
            service.is_active = False
            await self.session.flush()
    
    async def activate(self, service_id: int) -> None:
        """Activate service."""
        service = await self.get_by_id(service_id)
        if service:
            service.is_active = True
            await self.session.flush()
