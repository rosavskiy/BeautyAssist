"""Admin repository for analytics and management."""
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Master, Client, Appointment, Service, Expense, Payment, AdminBroadcast
from database.models.appointment import AppointmentStatus
from database.models.payment import PaymentStatus


class AdminRepository:
    """Repository for admin analytics and statistics."""
    
    def __init__(self, session: AsyncSession):
        """Initialize repository with database session."""
        self.session = session
    
    async def get_dashboard_stats(self) -> dict[str, Any]:
        """Get comprehensive dashboard statistics.
        
        Returns:
            dict: Dashboard statistics including:
                - total_masters: Total number of masters
                - active_masters: Masters with appointments in last 30 days
                - total_clients: Total number of clients
                - total_appointments: Total appointments count
                - completed_appointments: Completed appointments count
                - total_revenue: Sum of completed appointment payments
                - pending_revenue: Sum of pending appointment payments
                - total_expenses: Sum of all expenses
                - net_profit: total_revenue - total_expenses
        """
        now = datetime.utcnow()
        last_30_days = now - timedelta(days=30)
        
        # Total masters
        masters_result = await self.session.execute(
            select(func.count(Master.id))
        )
        total_masters = masters_result.scalar() or 0
        
        # Active masters (with appointments in last 30 days)
        active_masters_result = await self.session.execute(
            select(func.count(func.distinct(Appointment.master_id)))
            .where(Appointment.start_time >= last_30_days)
        )
        active_masters = active_masters_result.scalar() or 0
        
        # Total clients
        clients_result = await self.session.execute(
            select(func.count(Client.id))
        )
        total_clients = clients_result.scalar() or 0
        
        # Appointments stats
        appointments_result = await self.session.execute(
            select(
                func.count(Appointment.id).label("total"),
                func.sum(
                    case((Appointment.status == AppointmentStatus.COMPLETED, 1), else_=0)
                ).label("completed"),
            )
        )
        appointments_row = appointments_result.first()
        total_appointments = appointments_row.total or 0
        completed_appointments = appointments_row.completed or 0
        
        # Revenue from completed appointments
        revenue_result = await self.session.execute(
            select(func.coalesce(func.sum(Appointment.payment_amount), 0))
            .where(
                and_(
                    Appointment.status == AppointmentStatus.COMPLETED,
                    Appointment.payment_amount.isnot(None)
                )
            )
        )
        total_revenue = revenue_result.scalar() or 0
        
        # Pending revenue (completed but not paid)
        pending_revenue_result = await self.session.execute(
            select(func.coalesce(func.sum(Appointment.payment_amount), 0))
            .where(
                and_(
                    Appointment.status == AppointmentStatus.COMPLETED,
                    Appointment.payment_amount.is_(None)
                )
            )
        )
        pending_revenue = pending_revenue_result.scalar() or 0
        
        # Total expenses
        expenses_result = await self.session.execute(
            select(func.coalesce(func.sum(Expense.amount), 0))
        )
        total_expenses = expenses_result.scalar() or 0
        
        # Net profit
        net_profit = total_revenue - total_expenses
        
        return {
            "total_masters": total_masters,
            "active_masters": active_masters,
            "total_clients": total_clients,
            "total_appointments": total_appointments,
            "completed_appointments": completed_appointments,
            "total_revenue": float(total_revenue),
            "pending_revenue": float(pending_revenue),
            "total_expenses": float(total_expenses),
            "net_profit": float(net_profit),
        }
    
    async def get_masters_list(
        self, 
        limit: int = 50, 
        offset: int = 0,
        search_query: str | None = None,
        filter_premium: bool | None = None,
        filter_onboarded: bool | None = None
    ) -> list[Master]:
        """Get paginated list of masters with optional filters.
        
        Args:
            limit: Max number of results
            offset: Offset for pagination
            search_query: Search by name, username, phone
            filter_premium: Filter by premium status
            filter_onboarded: Filter by onboarding status
        
        Returns:
            List of Master objects
        """
        query = select(Master)
        
        # Apply filters
        conditions = []
        
        if search_query:
            search_pattern = f"%{search_query}%"
            conditions.append(
                or_(
                    Master.name.ilike(search_pattern),
                    Master.telegram_username.ilike(search_pattern),
                    Master.phone.ilike(search_pattern)
                )
            )
        
        if filter_premium is not None:
            conditions.append(Master.is_premium == filter_premium)
        
        if filter_onboarded is not None:
            conditions.append(Master.is_onboarded == filter_onboarded)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Order by registration date (newest first)
        query = query.order_by(Master.id.desc())
        
        # Apply pagination
        query = query.limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_master_stats(self, master_id: int) -> dict[str, Any]:
        """Get detailed statistics for specific master.
        
        Args:
            master_id: Master ID
        
        Returns:
            dict: Statistics including clients count, appointments, revenue
        """
        # Clients count
        clients_result = await self.session.execute(
            select(func.count(Client.id)).where(Client.master_id == master_id)
        )
        total_clients = clients_result.scalar() or 0
        
        # Services count
        services_result = await self.session.execute(
            select(func.count(Service.id)).where(Service.master_id == master_id)
        )
        total_services = services_result.scalar() or 0
        
        # Appointments stats
        appointments_result = await self.session.execute(
            select(
                func.count(Appointment.id).label("total"),
                func.sum(
                    case((Appointment.status == AppointmentStatus.COMPLETED, 1), else_=0)
                ).label("completed"),
                func.sum(
                    case((Appointment.status == AppointmentStatus.CANCELLED, 1), else_=0)
                ).label("cancelled"),
            ).where(Appointment.master_id == master_id)
        )
        appointments_row = appointments_result.first()
        
        # Revenue
        revenue_result = await self.session.execute(
            select(func.coalesce(func.sum(Appointment.payment_amount), 0))
            .where(
                and_(
                    Appointment.master_id == master_id,
                    Appointment.status == AppointmentStatus.COMPLETED,
                    Appointment.payment_amount.isnot(None)
                )
            )
        )
        total_revenue = revenue_result.scalar() or 0
        
        # Expenses
        expenses_result = await self.session.execute(
            select(func.coalesce(func.sum(Expense.amount), 0))
            .where(Expense.master_id == master_id)
        )
        total_expenses = expenses_result.scalar() or 0
        
        return {
            "total_clients": total_clients,
            "total_services": total_services,
            "total_appointments": appointments_row.total or 0,
            "completed_appointments": appointments_row.completed or 0,
            "cancelled_appointments": appointments_row.cancelled or 0,
            "total_revenue": float(total_revenue),
            "total_expenses": float(total_expenses),
            "net_profit": float(total_revenue - total_expenses),
        }
    
    async def create_broadcast(
        self, 
        content: str, 
        created_by: int,
        total_recipients: int,
        target_filter: str | None = None
    ) -> AdminBroadcast:
        """Create new broadcast record.
        
        Args:
            content: Message content
            created_by: Admin telegram_id
            total_recipients: Total target recipients count
            target_filter: Optional filter description
        
        Returns:
            Created AdminBroadcast object
        """
        broadcast = AdminBroadcast(
            content=content,
            created_by=created_by,
            total_recipients=total_recipients,
            target_filter=target_filter or "all"
        )
        self.session.add(broadcast)
        await self.session.commit()
        await self.session.refresh(broadcast)
        return broadcast
    
    async def update_broadcast_progress(
        self, 
        broadcast_id: int, 
        sent_count: int, 
        failed_count: int,
        is_completed: bool = False
    ) -> None:
        """Update broadcast sending progress.
        
        Args:
            broadcast_id: Broadcast ID
            sent_count: Number of successfully sent messages
            failed_count: Number of failed messages
            is_completed: Whether broadcast is completed
        """
        broadcast = await self.session.get(AdminBroadcast, broadcast_id)
        if not broadcast:
            return
        
        broadcast.sent_count = sent_count
        broadcast.failed_count = failed_count
        
        if is_completed:
            broadcast.is_completed = True
            broadcast.completed_at = datetime.utcnow()
        
        if not broadcast.started_at:
            broadcast.started_at = datetime.utcnow()
        
        await self.session.commit()
    
    async def get_recent_broadcasts(self, limit: int = 10) -> list[AdminBroadcast]:
        """Get recent broadcast history.
        
        Args:
            limit: Max number of results
        
        Returns:
            List of AdminBroadcast objects
        """
        result = await self.session.execute(
            select(AdminBroadcast)
            .order_by(AdminBroadcast.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_all_master_telegram_ids(self, filter_onboarded: bool = True) -> list[int]:
        """Get all master telegram IDs for broadcasting.
        
        Args:
            filter_onboarded: Only include onboarded masters
        
        Returns:
            List of telegram_ids
        """
        query = select(Master.telegram_id)
        
        if filter_onboarded:
            query = query.where(Master.is_onboarded == True)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_subscription_metrics(self) -> dict[str, Any]:
        """Get subscription business metrics.
        
        Returns:
            dict: Subscription metrics including:
                - mrr: Monthly Recurring Revenue
                - total_active_subscriptions: Count of active subscriptions
                - trial_conversions: Trial users who converted to paid
                - conversion_rate: Trial to paid conversion rate (%)
                - churn_rate: Monthly churn rate (%)
                - average_ltv: Average Customer Lifetime Value
                - revenue_by_plan: Revenue breakdown by plan type
        """
        from database.models.subscription import Subscription, SubscriptionStatus, SubscriptionPlan
        from database.models.transaction import Transaction, TransactionStatus
        
        now = datetime.utcnow()
        
        # MRR: Monthly Recurring Revenue from active subscriptions
        mrr_result = await self.session.execute(
            select(func.sum(
                case(
                    (Subscription.plan == SubscriptionPlan.MONTHLY.value, Subscription.amount),
                    (Subscription.plan == SubscriptionPlan.QUARTERLY.value, Subscription.amount / 3),
                    (Subscription.plan == SubscriptionPlan.YEARLY.value, Subscription.amount / 12),
                    else_=0
                )
            ))
            .where(Subscription.status == SubscriptionStatus.ACTIVE.value)
        )
        mrr = float(mrr_result.scalar() or 0)
        
        # Total active subscriptions
        active_subs_result = await self.session.execute(
            select(func.count(Subscription.id))
            .where(Subscription.status == SubscriptionStatus.ACTIVE.value)
        )
        total_active = active_subs_result.scalar() or 0
        
        # Trial conversions: count users who had trial and now have paid subscription
        trial_users_result = await self.session.execute(
            select(func.count(func.distinct(Subscription.master_id)))
            .where(Subscription.plan == SubscriptionPlan.TRIAL.value)
        )
        total_trial_users = trial_users_result.scalar() or 0
        
        converted_users_result = await self.session.execute(
            select(func.count(func.distinct(Subscription.master_id)))
            .where(
                and_(
                    Subscription.master_id.in_(
                        select(Subscription.master_id)
                        .where(Subscription.plan == SubscriptionPlan.TRIAL.value)
                    ),
                    Subscription.plan != SubscriptionPlan.TRIAL.value,
                    Subscription.status.in_([SubscriptionStatus.ACTIVE.value, SubscriptionStatus.EXPIRED.value])
                )
            )
        )
        converted_users = converted_users_result.scalar() or 0
        
        conversion_rate = (converted_users / total_trial_users * 100) if total_trial_users > 0 else 0
        
        # Churn rate: percentage of subscriptions that expired in last 30 days
        last_30_days = now - timedelta(days=30)
        
        active_30_days_ago_result = await self.session.execute(
            select(func.count(Subscription.id))
            .where(
                and_(
                    Subscription.start_date <= last_30_days,
                    Subscription.end_date > last_30_days,
                    Subscription.status == SubscriptionStatus.ACTIVE.value
                )
            )
        )
        active_30_days_ago = active_30_days_ago_result.scalar() or 0
        
        expired_last_30_result = await self.session.execute(
            select(func.count(Subscription.id))
            .where(
                and_(
                    Subscription.end_date.between(last_30_days, now),
                    Subscription.status == SubscriptionStatus.EXPIRED.value
                )
            )
        )
        expired_last_30 = expired_last_30_result.scalar() or 0
        
        churn_rate = (expired_last_30 / active_30_days_ago * 100) if active_30_days_ago > 0 else 0
        
        # Average LTV: Total revenue / Total unique paying customers
        total_revenue_result = await self.session.execute(
            select(func.sum(Transaction.amount))
            .where(
                and_(
                    Transaction.status == TransactionStatus.SUCCEEDED.value,
                    Transaction.type == 'subscription'
                )
            )
        )
        total_revenue = float(total_revenue_result.scalar() or 0)
        
        paying_customers_result = await self.session.execute(
            select(func.count(func.distinct(Subscription.master_id)))
            .where(
                and_(
                    Subscription.plan != SubscriptionPlan.TRIAL.value,
                    Subscription.status.in_([SubscriptionStatus.ACTIVE.value, SubscriptionStatus.EXPIRED.value])
                )
            )
        )
        paying_customers = paying_customers_result.scalar() or 0
        
        average_ltv = (total_revenue / paying_customers) if paying_customers > 0 else 0
        
        # Revenue by plan
        revenue_by_plan_result = await self.session.execute(
            select(
                Subscription.plan,
                func.sum(Subscription.amount).label('revenue')
            )
            .where(Subscription.status.in_([SubscriptionStatus.ACTIVE.value, SubscriptionStatus.EXPIRED.value]))
            .group_by(Subscription.plan)
        )
        revenue_by_plan = {row.plan: float(row.revenue or 0) for row in revenue_by_plan_result}
        
        return {
            'mrr': round(mrr, 2),
            'total_active_subscriptions': total_active,
            'trial_conversions': converted_users,
            'total_trial_users': total_trial_users,
            'conversion_rate': round(conversion_rate, 2),
            'churn_rate': round(churn_rate, 2),
            'average_ltv': round(average_ltv, 2),
            'revenue_by_plan': revenue_by_plan,
        }
