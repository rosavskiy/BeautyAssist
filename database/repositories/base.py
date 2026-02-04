"""
Base repository with common CRUD operations.

Provides a generic base class for all repositories to reduce code duplication.
"""
from typing import TypeVar, Generic, Optional, List, Type
from abc import ABC

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.base import Base

# Type variable for model classes
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(ABC, Generic[ModelType]):
    """
    Abstract base repository with common CRUD operations.
    
    Provides:
    - get_by_id: Get single entity by ID
    - get_all: Get all entities with optional limit
    - create: Create new entity (override in subclass for custom logic)
    - update: Update existing entity
    - delete: Delete entity by ID
    - count: Count all entities
    - exists: Check if entity exists by ID
    
    Usage:
        class MasterRepository(BaseRepository[Master]):
            model_class = Master
            
            async def get_by_telegram_id(self, telegram_id: int):
                # Custom method
                ...
    """
    
    model_class: Type[ModelType]
    
    def __init__(self, session: AsyncSession):
        """Initialize repository with database session."""
        self.session = session
    
    async def get_by_id(self, entity_id: int) -> Optional[ModelType]:
        """
        Get entity by its primary key ID.
        
        Args:
            entity_id: Primary key ID
            
        Returns:
            Entity or None if not found
        """
        result = await self.session.execute(
            select(self.model_class).where(self.model_class.id == entity_id)
        )
        return result.scalar_one_or_none()
    
    async def get_all(self, limit: Optional[int] = None) -> List[ModelType]:
        """
        Get all entities.
        
        Args:
            limit: Optional maximum number of results
            
        Returns:
            List of entities
        """
        query = select(self.model_class)
        if limit:
            query = query.limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def update(self, entity: ModelType) -> ModelType:
        """
        Update entity in database.
        
        Note: The entity must already be attached to the session.
        Changes are flushed but not committed.
        
        Args:
            entity: Entity to update
            
        Returns:
            Updated entity
        """
        await self.session.flush()
        return entity
    
    async def delete(self, entity_id: int) -> bool:
        """
        Delete entity by ID.
        
        Args:
            entity_id: Primary key ID
            
        Returns:
            True if deleted, False if not found
        """
        entity = await self.get_by_id(entity_id)
        if entity:
            await self.session.delete(entity)
            await self.session.flush()
            return True
        return False
    
    async def count(self) -> int:
        """
        Count all entities.
        
        Returns:
            Total count of entities
        """
        result = await self.session.execute(
            select(func.count(self.model_class.id))
        )
        return result.scalar() or 0
    
    async def exists(self, entity_id: int) -> bool:
        """
        Check if entity exists by ID.
        
        Args:
            entity_id: Primary key ID
            
        Returns:
            True if exists, False otherwise
        """
        result = await self.session.execute(
            select(func.count(self.model_class.id)).where(
                self.model_class.id == entity_id
            )
        )
        return (result.scalar() or 0) > 0
    
    def add(self, entity: ModelType) -> None:
        """
        Add entity to session (for create operations).
        
        Args:
            entity: Entity to add
        """
        self.session.add(entity)
    
    async def flush(self) -> None:
        """Flush session changes to database."""
        await self.session.flush()
    
    async def refresh(self, entity: ModelType) -> ModelType:
        """
        Refresh entity from database.
        
        Args:
            entity: Entity to refresh
            
        Returns:
            Refreshed entity
        """
        await self.session.refresh(entity)
        return entity
