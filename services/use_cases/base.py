"""
Base use case class with common functionality.
"""
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Any

from sqlalchemy.ext.asyncio import AsyncSession


ResultType = TypeVar("ResultType")


class BaseUseCase(ABC, Generic[ResultType]):
    """
    Abstract base class for use cases.
    
    A use case encapsulates a single business operation and orchestrates
    the interactions between repositories, services, and other components.
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize use case with database session.
        
        Args:
            session: Async SQLAlchemy session for database operations
        """
        self.session = session
    
    @abstractmethod
    async def execute(self, *args, **kwargs) -> ResultType:
        """
        Execute the use case.
        
        Subclasses must implement this method with their specific logic.
        
        Returns:
            Result of the use case execution
        """
        pass
