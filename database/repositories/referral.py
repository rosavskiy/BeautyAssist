"""Referral repository for database operations."""
from typing import Optional, List, Dict
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Referral, ReferralStatus


class ReferralRepository:
    """Repository for Referral model operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(
        self,
        referrer_id: int,
        referred_id: int,
        reward_days: int = 7
    ) -> Referral:
        """Create new referral record."""
        referral = Referral(
            referrer_id=referrer_id,
            referred_id=referred_id,
            status=ReferralStatus.PENDING.value,
            reward_given=False,
            reward_days=reward_days
        )
        self.session.add(referral)
        await self.session.commit()
        await self.session.refresh(referral)
        return referral
    
    async def get_by_id(self, referral_id: int) -> Optional[Referral]:
        """Get referral by ID."""
        result = await self.session.execute(
            select(Referral).where(Referral.id == referral_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_referred_id(self, referred_id: int) -> Optional[Referral]:
        """Get referral record by referred master ID."""
        result = await self.session.execute(
            select(Referral).where(Referral.referred_id == referred_id)
        )
        return result.scalar_one_or_none()
    
    async def get_all_by_referrer(
        self,
        referrer_id: int,
        status: Optional[ReferralStatus] = None
    ) -> List[Referral]:
        """Get all referrals by referrer, optionally filtered by status."""
        query = select(Referral).where(Referral.referrer_id == referrer_id)
        
        if status:
            query = query.where(Referral.status == status.value)
        
        query = query.order_by(Referral.created_at.desc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def activate(self, referral_id: int) -> Optional[Referral]:
        """Mark referral as activated."""
        referral = await self.get_by_id(referral_id)
        if not referral:
            return None
        
        referral.status = ReferralStatus.ACTIVATED.value
        referral.activated_at = datetime.utcnow()
        referral.reward_given = True
        
        await self.session.commit()
        await self.session.refresh(referral)
        return referral
    
    async def expire_old_referrals(self, days: int = 30) -> int:
        """Expire referrals older than N days without activation."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Find pending referrals older than cutoff
        result = await self.session.execute(
            select(Referral).where(
                and_(
                    Referral.status == ReferralStatus.PENDING.value,
                    Referral.created_at < cutoff_date
                )
            )
        )
        referrals = result.scalars().all()
        
        count = 0
        for referral in referrals:
            referral.status = ReferralStatus.EXPIRED.value
            count += 1
        
        await self.session.commit()
        return count
    
    async def get_statistics(self, referrer_id: int) -> Dict[str, int]:
        """Get referral statistics for a master."""
        # Count by status
        result = await self.session.execute(
            select(
                Referral.status,
                func.count(Referral.id).label('count')
            ).where(
                Referral.referrer_id == referrer_id
            ).group_by(Referral.status)
        )
        
        stats = {
            'pending': 0,
            'activated': 0,
            'expired': 0,
            'total_reward_days': 0
        }
        
        for status, count in result:
            stats[status] = count
        
        # Calculate total reward days
        reward_result = await self.session.execute(
            select(func.sum(Referral.reward_days)).where(
                and_(
                    Referral.referrer_id == referrer_id,
                    Referral.status == ReferralStatus.ACTIVATED.value,
                    Referral.reward_given == True
                )
            )
        )
        total_days = reward_result.scalar()
        stats['total_reward_days'] = total_days or 0
        
        return stats
    
    async def check_duplicate(self, referrer_id: int, referred_id: int) -> bool:
        """Check if referral already exists."""
        result = await self.session.execute(
            select(Referral).where(
                and_(
                    Referral.referrer_id == referrer_id,
                    Referral.referred_id == referred_id
                )
            )
        )
        return result.scalar_one_or_none() is not None
    
    async def get_pending_count(self, referrer_id: int) -> int:
        """Get count of pending referrals."""
        result = await self.session.execute(
            select(func.count(Referral.id)).where(
                and_(
                    Referral.referrer_id == referrer_id,
                    Referral.status == ReferralStatus.PENDING.value
                )
            )
        )
        return result.scalar() or 0
    
    async def get_activated_count(self, referrer_id: int) -> int:
        """Get count of activated referrals."""
        result = await self.session.execute(
            select(func.count(Referral.id)).where(
                and_(
                    Referral.referrer_id == referrer_id,
                    Referral.status == ReferralStatus.ACTIVATED.value
                )
            )
        )
        return result.scalar() or 0
