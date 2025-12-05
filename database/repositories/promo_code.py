"""PromoCode repository for managing promo codes."""
from datetime import datetime
from typing import Sequence

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.promo_code import (
    PromoCode,
    PromoCodeUsage,
    PromoCodeType,
    PromoCodeStatus,
)


class PromoCodeRepository:
    """Repository for promo code operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_promo_code(
        self,
        code: str,
        type: PromoCodeType,
        discount_percent: int | None = None,
        discount_amount: int | None = None,
        trial_days: int | None = None,
        valid_until: datetime | None = None,
        max_uses: int | None = None,
        max_uses_per_user: int = 1,
        description: str | None = None,
        created_by: int | None = None,
    ) -> PromoCode:
        """Create a new promo code."""
        promo_code = PromoCode(
            code=code.upper(),
            type=type.value,
            discount_percent=discount_percent,
            discount_amount=discount_amount,
            trial_days=trial_days,
            status=PromoCodeStatus.ACTIVE.value,
            valid_until=valid_until,
            max_uses=max_uses,
            max_uses_per_user=max_uses_per_user,
            description=description,
            created_by=created_by,
        )
        self.session.add(promo_code)
        await self.session.flush()
        return promo_code
    
    async def get_promo_code(self, code: str) -> PromoCode | None:
        """Get promo code by code string."""
        query = select(PromoCode).where(PromoCode.code == code.upper())
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def validate_promo_code(
        self,
        code: str,
        master_id: int,
    ) -> tuple[bool, str | None, PromoCode | None]:
        """
        Validate promo code for master.
        
        Returns:
            (is_valid, error_message, promo_code)
        """
        promo_code = await self.get_promo_code(code)
        
        if not promo_code:
            return False, "Промокод не найден", None
        
        if not promo_code.is_valid:
            if promo_code.status == PromoCodeStatus.EXPIRED.value:
                return False, "Промокод истёк", None
            if promo_code.status == PromoCodeStatus.DEPLETED.value:
                return False, "Промокод исчерпан", None
            if promo_code.status == PromoCodeStatus.INACTIVE.value:
                return False, "Промокод деактивирован", None
            return False, "Промокод недействителен", None
        
        # Check user usage
        usage_count = await self.get_user_usage_count(promo_code.id, master_id)
        if usage_count >= promo_code.max_uses_per_user:
            return False, f"Вы уже использовали этот промокод (лимит: {promo_code.max_uses_per_user})", None
        
        return True, None, promo_code
    
    async def apply_promo_code(
        self,
        promo_code: PromoCode,
        master_id: int,
        subscription_id: int,
        original_amount: int,
    ) -> tuple[int, int]:
        """
        Apply promo code and create usage record.
        
        Returns:
            (discount_amount, final_amount)
        """
        # Calculate discount
        if promo_code.type == PromoCodeType.PERCENT.value:
            discount_amount = int(original_amount * promo_code.discount_percent / 100)
        elif promo_code.type == PromoCodeType.FIXED.value:
            discount_amount = min(promo_code.discount_amount, original_amount)
        else:
            discount_amount = 0
        
        final_amount = max(0, original_amount - discount_amount)
        
        # Create usage record
        usage = PromoCodeUsage(
            promo_code_id=promo_code.id,
            master_id=master_id,
            subscription_id=subscription_id,
            discount_amount=discount_amount,
            original_amount=original_amount,
            final_amount=final_amount,
        )
        self.session.add(usage)
        
        # Increment usage counter
        promo_code.current_uses += 1
        
        # Check if depleted
        if promo_code.max_uses and promo_code.current_uses >= promo_code.max_uses:
            promo_code.status = PromoCodeStatus.DEPLETED.value
        
        await self.session.flush()
        
        return discount_amount, final_amount
    
    async def get_user_usage_count(self, promo_code_id: int, master_id: int) -> int:
        """Get how many times user has used this promo code."""
        query = select(func.count(PromoCodeUsage.id)).where(
            and_(
                PromoCodeUsage.promo_code_id == promo_code_id,
                PromoCodeUsage.master_id == master_id,
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one()
    
    async def get_all_promo_codes(
        self,
        status: PromoCodeStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[PromoCode]:
        """Get all promo codes with filters."""
        query = select(PromoCode)
        
        if status:
            # Handle both string and PromoCodeStatus enum
            status_value = status.value if hasattr(status, 'value') else status
            query = query.where(PromoCode.status == status_value)
        
        query = query.order_by(PromoCode.created_at.desc()).limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def deactivate_promo_code(self, code: str) -> PromoCode | None:
        """Deactivate promo code."""
        promo_code = await self.get_promo_code(code)
        if promo_code:
            promo_code.status = PromoCodeStatus.INACTIVE.value
            await self.session.flush()
        return promo_code
    
    async def get_promo_code_stats(self, code: str) -> dict:
        """Get usage statistics for promo code."""
        promo_code = await self.get_promo_code(code)
        if not promo_code:
            return {}
        
        # Get usage count
        usage_query = select(func.count(PromoCodeUsage.id)).where(
            PromoCodeUsage.promo_code_id == promo_code.id
        )
        usage_result = await self.session.execute(usage_query)
        usage_count = usage_result.scalar_one()
        
        # Get total discount given
        discount_query = select(func.sum(PromoCodeUsage.discount_amount)).where(
            PromoCodeUsage.promo_code_id == promo_code.id
        )
        discount_result = await self.session.execute(discount_query)
        total_discount = discount_result.scalar_one() or 0
        
        return {
            "code": promo_code.code,
            "type": promo_code.type,
            "status": promo_code.status,
            "usage_count": usage_count,
            "max_uses": promo_code.max_uses,
            "total_discount_given": total_discount,
            "current_uses": promo_code.current_uses,
        }
