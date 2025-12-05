"""Database base configuration and session management."""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from bot.config import settings


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# Create async engine
engine = create_async_engine(
    str(settings.database_url),
    echo=settings.debug,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    poolclass=NullPool if settings.debug else None,
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


class DBSession:
    """Context manager wrapper for get_db()."""
    
    def __init__(self):
        self._gen = None
        self._session = None
    
    async def __aenter__(self) -> AsyncSession:
        self._gen = get_db()
        self._session = await self._gen.__anext__()
        return self._session
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._gen:
            try:
                await self._gen.__anext__()
            except StopAsyncIteration:
                pass


async def init_db():
    """Initialize database - create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Best-effort schema compatibility tweaks for dev environments
        try:
            await conn.exec_driver_sql("ALTER TABLE masters ADD COLUMN IF NOT EXISTS city VARCHAR(255)")
        except Exception:
            pass


async def close_db():
    """Close database connections."""
    await engine.dispose()
