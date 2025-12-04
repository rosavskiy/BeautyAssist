"""Master repository for database operations."""
from typing import Optional
import secrets
import string

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Master


class MasterRepository:
    """Repository for Master model operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, master_id: int) -> Optional[Master]:
        """Get master by ID."""
        result = await self.session.execute(
            select(Master).where(Master.id == master_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[Master]:
        """Get master by Telegram ID."""
        result = await self.session.execute(
            select(Master).where(Master.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_referral_code(self, referral_code: str) -> Optional[Master]:
        """Get master by referral code."""
        result = await self.session.execute(
            select(Master).where(Master.referral_code == referral_code)
        )
        return result.scalar_one_or_none()
    
    async def get_all(self) -> list[Master]:
        """Get all masters."""
        result = await self.session.execute(select(Master))
        return list(result.scalars().all())
    
    async def create(
        self,
        telegram_id: int,
        name: str,
        telegram_username: Optional[str] = None,
        phone: Optional[str] = None,
        timezone: str = "Europe/Moscow",
    ) -> Master:
        """Create new master."""
        # Generate unique referral code
        referral_code = self._generate_referral_code()
        while await self.get_by_referral_code(referral_code):
            referral_code = self._generate_referral_code()
        
        master = Master(
            telegram_id=telegram_id,
            telegram_username=telegram_username,
            name=name,
            phone=phone,
            timezone=timezone,
            referral_code=referral_code,
            work_schedule={},
            is_onboarded=False,
        )
        
        self.session.add(master)
        await self.session.flush()
        return master
    
    async def update(self, master: Master) -> Master:
        """Update master."""
        await self.session.flush()
        return master
    
    async def set_onboarded(self, master_id: int) -> None:
        """Mark master as onboarded."""
        master = await self.get_by_id(master_id)
        if master:
            master.is_onboarded = True
            await self.session.flush()
    
    def _generate_referral_code(self, length: int = 8) -> str:
        """Generate random referral code."""
        alphabet = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
