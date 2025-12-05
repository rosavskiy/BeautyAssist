"""Subscription repository for managing user subscriptions."""
from datetime import datetime, timedelta
from typing import Sequence

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.subscription import (
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    PaymentMethod,
)
from database.models.transaction import Transaction, TransactionStatus, TransactionType


class SubscriptionRepository:
    """Repository for subscription operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_subscription(
        self,
        master_id: int,
        plan: SubscriptionPlan,
        start_date: datetime,
        end_date: datetime,
        amount: int,
        currency: str = "RUB",
        payment_method: PaymentMethod | None = None,
        auto_renew: bool = False,
    ) -> Subscription:
        """Create a new subscription."""
        subscription = Subscription(
            master_id=master_id,
            plan=plan.value,
            status=SubscriptionStatus.PENDING.value,
            start_date=start_date,
            end_date=end_date,
            amount=amount,
            currency=currency,
            payment_method=payment_method.value if payment_method else None,
            auto_renew=auto_renew,
        )
        self.session.add(subscription)
        await self.session.flush()
        return subscription
    
    async def get_active_subscription(self, master_id: int) -> Subscription | None:
        """Get active subscription for master."""
        query = select(Subscription).where(
            and_(
                Subscription.master_id == master_id,
                Subscription.status == SubscriptionStatus.ACTIVE.value,
                Subscription.end_date > func.now(),
            )
        ).order_by(Subscription.end_date.desc())
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_subscription_by_id(self, subscription_id: int) -> Subscription | None:
        """Get subscription by ID."""
        query = select(Subscription).where(Subscription.id == subscription_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_master_subscriptions(
        self,
        master_id: int,
        limit: int = 10,
        offset: int = 0,
    ) -> Sequence[Subscription]:
        """Get all subscriptions for master (history)."""
        query = (
            select(Subscription)
            .where(Subscription.master_id == master_id)
            .order_by(Subscription.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def activate_subscription(self, subscription_id: int) -> Subscription:
        """Activate subscription (after successful payment)."""
        subscription = await self.get_subscription_by_id(subscription_id)
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")
        
        subscription.status = SubscriptionStatus.ACTIVE.value
        await self.session.flush()
        return subscription
    
    async def cancel_subscription(
        self,
        subscription_id: int,
        reason: str | None = None,
    ) -> Subscription:
        """Cancel subscription."""
        subscription = await self.get_subscription_by_id(subscription_id)
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")
        
        subscription.status = SubscriptionStatus.CANCELLED.value
        subscription.cancelled_at = func.now()
        subscription.cancellation_reason = reason
        subscription.auto_renew = False
        await self.session.flush()
        return subscription
    
    async def expire_subscription(self, subscription_id: int) -> Subscription:
        """Mark subscription as expired."""
        subscription = await self.get_subscription_by_id(subscription_id)
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")
        
        subscription.status = SubscriptionStatus.EXPIRED.value
        await self.session.flush()
        return subscription
    
    async def is_trial_available(self, master_id: int) -> bool:
        """Check if trial is available for master."""
        query = select(func.count(Subscription.id)).where(
            and_(
                Subscription.master_id == master_id,
                Subscription.plan == SubscriptionPlan.TRIAL.value,
            )
        )
        result = await self.session.execute(query)
        trial_count = result.scalar_one()
        return trial_count == 0
    
    async def check_access(self, master_id: int) -> bool:
        """Check if master has active subscription."""
        subscription = await self.get_active_subscription(master_id)
        return subscription is not None and subscription.is_active
    
    async def get_expiring_soon(
        self,
        days: int = 3,
        statuses: list[SubscriptionStatus] | None = None,
    ) -> Sequence[Subscription]:
        """Get subscriptions expiring in N days."""
        if statuses is None:
            statuses = [SubscriptionStatus.ACTIVE]
        
        expiration_date = func.now() + timedelta(days=days)
        
        query = select(Subscription).where(
            and_(
                Subscription.status.in_([s.value for s in statuses]),
                Subscription.end_date <= expiration_date,
                Subscription.end_date > func.now(),
            )
        ).order_by(Subscription.end_date.asc())
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_expired_subscriptions(
        self,
        limit: int = 100,
    ) -> Sequence[Subscription]:
        """Get subscriptions that expired but status is still active."""
        query = (
            select(Subscription)
            .where(
                and_(
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                    Subscription.end_date <= func.now(),
                )
            )
            .limit(limit)
        )
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def create_transaction(
        self,
        master_id: int,
        subscription_id: int | None,
        type: TransactionType,
        amount: int,
        currency: str,
        payment_method: PaymentMethod,
        description: str | None = None,
        provider_payment_id: str | None = None,
        provider_data: dict | None = None,
    ) -> Transaction:
        """Create payment transaction."""
        transaction = Transaction(
            subscription_id=subscription_id,
            master_id=master_id,
            type=type.value,
            status=TransactionStatus.PENDING.value,
            amount=amount,
            currency=currency,
            payment_method=payment_method.value,
            description=description,
            provider_payment_id=provider_payment_id,
            provider_data=provider_data,
        )
        self.session.add(transaction)
        await self.session.flush()
        return transaction
    
    async def update_transaction_status(
        self,
        transaction_id: int,
        status: TransactionStatus,
        error_code: str | None = None,
        error_message: str | None = None,
        provider_data: dict | None = None,
    ) -> Transaction:
        """Update transaction status."""
        query = select(Transaction).where(Transaction.id == transaction_id)
        result = await self.session.execute(query)
        transaction = result.scalar_one_or_none()
        
        if not transaction:
            raise ValueError(f"Transaction {transaction_id} not found")
        
        transaction.status = status.value
        transaction.error_code = error_code
        transaction.error_message = error_message
        
        if provider_data:
            transaction.provider_data = provider_data
        
        if status in [TransactionStatus.SUCCEEDED, TransactionStatus.FAILED]:
            transaction.completed_at = func.now()
        
        await self.session.flush()
        return transaction
    
    async def get_transaction_by_provider_id(
        self,
        provider_payment_id: str,
    ) -> Transaction | None:
        """Get transaction by provider payment ID."""
        query = select(Transaction).where(
            Transaction.provider_payment_id == provider_payment_id
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_master_transactions(
        self,
        master_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> Sequence[Transaction]:
        """Get transaction history for master."""
        query = (
            select(Transaction)
            .where(Transaction.master_id == master_id)
            .order_by(Transaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_revenue_stats(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict:
        """Get revenue statistics for admin."""
        filters = [Transaction.status == TransactionStatus.SUCCEEDED.value]
        
        if start_date:
            filters.append(Transaction.created_at >= start_date)
        if end_date:
            filters.append(Transaction.created_at <= end_date)
        
        # Total revenue
        query = select(
            func.count(Transaction.id),
            func.sum(Transaction.amount),
            func.avg(Transaction.amount),
        ).where(and_(*filters))
        
        result = await self.session.execute(query)
        count, total, avg = result.one()
        
        # Revenue by plan
        plan_query = select(
            Subscription.plan,
            func.count(Transaction.id),
            func.sum(Transaction.amount),
        ).select_from(Transaction).join(
            Subscription,
            Transaction.subscription_id == Subscription.id,
        ).where(
            and_(*filters)
        ).group_by(Subscription.plan)
        
        plan_result = await self.session.execute(plan_query)
        by_plan = {row[0]: {"count": row[1], "total": row[2]} for row in plan_result.all()}
        
        return {
            "total_transactions": count or 0,
            "total_revenue": int(total or 0),
            "average_transaction": int(avg or 0),
            "by_plan": by_plan,
        }
