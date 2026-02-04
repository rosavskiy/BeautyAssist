"""
Helper functions for handler operations.

Provides convenience wrappers for common handler patterns.
"""
from typing import Type, TypeVar, Callable, Any
from contextlib import asynccontextmanager

from database.base import async_session_maker
from services.use_cases.base import BaseUseCase

UseCaseType = TypeVar("UseCaseType", bound=BaseUseCase)


@asynccontextmanager
async def use_case_context(use_case_class: Type[UseCaseType]):
    """
    Context manager for use case execution.
    
    Creates a database session and instantiates the use case.
    Handles commit/rollback automatically.
    
    Usage:
        async with use_case_context(GetAppointmentsUseCase) as uc:
            result = await uc.execute(telegram_id=123, days=7)
    """
    async with async_session_maker() as session:
        try:
            use_case = use_case_class(session)
            yield use_case
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def run_use_case(
    use_case_class: Type[UseCaseType],
    *args,
    **kwargs
) -> Any:
    """
    Run a use case with automatic session management.
    
    Creates session, executes use case, and handles commit/rollback.
    
    Usage:
        result = await run_use_case(
            GetAppointmentsUseCase,
            telegram_id=123,
            days=7
        )
    """
    async with use_case_context(use_case_class) as uc:
        return await uc.execute(*args, **kwargs)
