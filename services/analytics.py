"""Analytics service for admin metrics and insights."""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, and_, case, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Master, Appointment, Service, Subscription, Transaction
from database.models.appointment import AppointmentStatus
from database.models.subscription import SubscriptionStatus

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for advanced analytics and business metrics."""
    
    def __init__(self, session: AsyncSession):
        """Initialize analytics service with database session."""
        self.session = session
    
    async def get_retention_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, float]:
        """Calculate user retention metrics.
        
        Retention shows what percentage of users return after N days:
        - Day 1: % of users active on day after registration
        - Day 7: % of users active 7 days after registration
        - Day 30: % of users active 30 days after registration
        
        Args:
            start_date: Start date for cohort (defaults to 30 days ago)
            end_date: End date for cohort (defaults to today)
            
        Returns:
            dict: Retention percentages {day1: float, day7: float, day30: float}
        """
        try:
            if not end_date:
                end_date = datetime.utcnow()
            if not start_date:
                start_date = end_date - timedelta(days=30)
            
            # Get all masters registered in period
            registered_result = await self.session.execute(
                select(Master.id, Master.created_at)
                .where(
                    and_(
                        Master.created_at >= start_date,
                        Master.created_at <= end_date
                    )
                )
            )
            registered_masters = registered_result.all()
            total_registered = len(registered_masters)
            
            if total_registered == 0:
                return {"day1": 0.0, "day7": 0.0, "day30": 0.0}
            
            # Calculate retention for each period
            retention_metrics = {}
            
            for days, key in [(1, "day1"), (7, "day7"), (30, "day30")]:
                active_count = 0
                
                for master_id, created_at in registered_masters:
                    # Check if master was active N days after registration
                    target_date = created_at + timedelta(days=days)
                    next_day = target_date + timedelta(days=1)
                    
                    # Skip if target date is in the future
                    if target_date > datetime.utcnow():
                        continue
                    
                    # Check for appointments on target day
                    activity_result = await self.session.execute(
                        select(func.count(Appointment.id))
                        .where(
                            and_(
                                Appointment.master_id == master_id,
                                Appointment.start_time >= target_date,
                                Appointment.start_time < next_day
                            )
                        )
                    )
                    
                    if activity_result.scalar() > 0:
                        active_count += 1
                
                # Calculate percentage
                eligible_count = sum(
                    1 for _, created_at in registered_masters
                    if created_at + timedelta(days=days) <= datetime.utcnow()
                )
                
                retention_metrics[key] = (
                    (active_count / eligible_count * 100)
                    if eligible_count > 0
                    else 0.0
                )
            
            logger.info(
                f"Retention calculated: {retention_metrics} "
                f"(total registered: {total_registered})"
            )
            return retention_metrics
            
        except Exception as e:
            logger.error(f"Error calculating retention report: {e}", exc_info=True)
            return {"day1": 0.0, "day7": 0.0, "day30": 0.0}
    
    async def get_cohort_analysis(
        self,
        cohort_weeks: int = 8
    ) -> List[Dict[str, Any]]:
        """Perform cohort analysis grouped by registration week.
        
        Groups users by week of registration and tracks their retention
        over time (Day 0, Day 7, Day 14, Day 30).
        
        Args:
            cohort_weeks: Number of weeks to analyze (default: 8)
            
        Returns:
            list: Cohort data with retention percentages
                [{
                    "cohort_week": "2025-W48",
                    "cohort_start": datetime,
                    "registered": 15,
                    "day0": 100.0,
                    "day7": 80.0,
                    "day14": 66.7,
                    "day30": 53.3
                }]
        """
        try:
            cohorts = []
            end_date = datetime.utcnow()
            
            for week_offset in range(cohort_weeks):
                # Calculate cohort week boundaries
                cohort_end = end_date - timedelta(weeks=week_offset)
                cohort_start = cohort_end - timedelta(weeks=1)
                
                # Get masters registered in this week
                registered_result = await self.session.execute(
                    select(Master.id, Master.created_at)
                    .where(
                        and_(
                            Master.created_at >= cohort_start,
                            Master.created_at < cohort_end
                        )
                    )
                )
                cohort_masters = registered_result.all()
                registered_count = len(cohort_masters)
                
                if registered_count == 0:
                    continue
                
                # Calculate retention for different periods
                retention_data = {
                    "cohort_week": f"{cohort_start.year}-W{cohort_start.isocalendar()[1]:02d}",
                    "cohort_start": cohort_start.isoformat(),
                    "registered": registered_count,
                    "day0": 100.0  # All users are active on day 0
                }
                
                # Calculate retention for days 7, 14, 30
                for days in [7, 14, 30]:
                    active_count = 0
                    eligible_count = 0
                    
                    for master_id, created_at in cohort_masters:
                        target_date = created_at + timedelta(days=days)
                        
                        # Skip if target date is in the future
                        if target_date > datetime.utcnow():
                            continue
                        
                        eligible_count += 1
                        
                        # Check activity
                        next_day = target_date + timedelta(days=1)
                        activity_result = await self.session.execute(
                            select(func.count(Appointment.id))
                            .where(
                                and_(
                                    Appointment.master_id == master_id,
                                    Appointment.start_time >= target_date,
                                    Appointment.start_time < next_day
                                )
                            )
                        )
                        
                        if activity_result.scalar() > 0:
                            active_count += 1
                    
                    retention_pct = (
                        (active_count / eligible_count * 100)
                        if eligible_count > 0
                        else 0.0
                    )
                    retention_data[f"day{days}"] = round(retention_pct, 1)
                
                cohorts.append(retention_data)
            
            logger.info(f"Cohort analysis completed: {len(cohorts)} cohorts")
            return cohorts
            
        except Exception as e:
            logger.error(f"Error in cohort analysis: {e}", exc_info=True)
            return []
    
    async def get_funnel_conversion(self) -> Dict[str, Any]:
        """Calculate conversion funnel metrics.
        
        Tracks user progression through key milestones:
        1. Registered
        2. Completed onboarding
        3. Created first service
        4. Received first booking
        5. Paid for subscription
        
        Returns:
            dict: Funnel stages with counts and conversion rates
                {
                    "registered": {"count": 100, "rate": 100.0},
                    "onboarded": {"count": 85, "rate": 85.0},
                    "first_service": {"count": 72, "rate": 72.0},
                    "first_booking": {"count": 58, "rate": 58.0},
                    "paid": {"count": 45, "rate": 45.0}
                }
        """
        try:
            # 1. Total registered masters
            registered_result = await self.session.execute(
                select(func.count(Master.id))
            )
            total_registered = registered_result.scalar() or 0
            
            if total_registered == 0:
                return {
                    "registered": {"count": 0, "rate": 100.0},
                    "onboarded": {"count": 0, "rate": 0.0},
                    "first_service": {"count": 0, "rate": 0.0},
                    "first_booking": {"count": 0, "rate": 0.0},
                    "paid": {"count": 0, "rate": 0.0}
                }
            
            # 2. Completed onboarding
            onboarded_result = await self.session.execute(
                select(func.count(Master.id))
                .where(Master.is_onboarded == True)
            )
            onboarded_count = onboarded_result.scalar() or 0
            
            # 3. Created at least one service
            first_service_result = await self.session.execute(
                select(func.count(distinct(Service.master_id)))
            )
            first_service_count = first_service_result.scalar() or 0
            
            # 4. Received at least one booking
            first_booking_result = await self.session.execute(
                select(func.count(distinct(Appointment.master_id)))
            )
            first_booking_count = first_booking_result.scalar() or 0
            
            # 5. Paid for subscription (non-trial)
            paid_result = await self.session.execute(
                select(func.count(distinct(Subscription.master_id)))
                .where(
                    and_(
                        Subscription.status == SubscriptionStatus.ACTIVE.value,
                        Subscription.plan != 'trial'
                    )
                )
            )
            paid_count = paid_result.scalar() or 0
            
            # Calculate conversion rates
            funnel = {
                "registered": {
                    "count": total_registered,
                    "rate": 100.0
                },
                "onboarded": {
                    "count": onboarded_count,
                    "rate": round((onboarded_count / total_registered * 100), 1)
                },
                "first_service": {
                    "count": first_service_count,
                    "rate": round((first_service_count / total_registered * 100), 1)
                },
                "first_booking": {
                    "count": first_booking_count,
                    "rate": round((first_booking_count / total_registered * 100), 1)
                },
                "paid": {
                    "count": paid_count,
                    "rate": round((paid_count / total_registered * 100), 1)
                }
            }
            
            logger.info(f"Funnel conversion calculated: {funnel}")
            return funnel
            
        except Exception as e:
            logger.error(f"Error calculating funnel conversion: {e}", exc_info=True)
            return {
                "registered": {"count": 0, "rate": 100.0},
                "onboarded": {"count": 0, "rate": 0.0},
                "first_service": {"count": 0, "rate": 0.0},
                "first_booking": {"count": 0, "rate": 0.0},
                "paid": {"count": 0, "rate": 0.0}
            }
    
    async def get_growth_metrics(
        self,
        period: str = 'month'
    ) -> Dict[str, Any]:
        """Calculate growth metrics (DAU, WAU, MAU, growth rate).
        
        Args:
            period: Time period for analysis ('day', 'week', 'month')
            
        Returns:
            dict: Growth metrics
                {
                    "dau": 234,  # Daily Active Users
                    "wau": 1523,  # Weekly Active Users
                    "mau": 4891,  # Monthly Active Users
                    "growth_rate": 12.5,  # % growth vs previous period
                    "activation_rate": 68.5  # % of registered who are active
                }
        """
        try:
            now = datetime.utcnow()
            
            # Calculate DAU (masters with appointments today)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow = today_start + timedelta(days=1)
            
            dau_result = await self.session.execute(
                select(func.count(distinct(Appointment.master_id)))
                .where(
                    and_(
                        Appointment.start_time >= today_start,
                        Appointment.start_time < tomorrow
                    )
                )
            )
            dau = dau_result.scalar() or 0
            
            # Calculate WAU (masters with appointments in last 7 days)
            week_ago = now - timedelta(days=7)
            wau_result = await self.session.execute(
                select(func.count(distinct(Appointment.master_id)))
                .where(Appointment.start_time >= week_ago)
            )
            wau = wau_result.scalar() or 0
            
            # Calculate MAU (masters with appointments in last 30 days)
            month_ago = now - timedelta(days=30)
            mau_result = await self.session.execute(
                select(func.count(distinct(Appointment.master_id)))
                .where(Appointment.start_time >= month_ago)
            )
            mau = mau_result.scalar() or 0
            
            # Calculate growth rate (compare current period with previous)
            if period == 'month':
                # Current month registrations
                month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                current_result = await self.session.execute(
                    select(func.count(Master.id))
                    .where(Master.created_at >= month_start)
                )
                current_period = current_result.scalar() or 0
                
                # Previous month registrations
                prev_month_end = month_start - timedelta(seconds=1)
                prev_month_start = prev_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                previous_result = await self.session.execute(
                    select(func.count(Master.id))
                    .where(
                        and_(
                            Master.created_at >= prev_month_start,
                            Master.created_at < month_start
                        )
                    )
                )
                previous_period = previous_result.scalar() or 0
                
            elif period == 'week':
                # Current week
                week_start = now - timedelta(days=now.weekday())
                week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
                current_result = await self.session.execute(
                    select(func.count(Master.id))
                    .where(Master.created_at >= week_start)
                )
                current_period = current_result.scalar() or 0
                
                # Previous week
                prev_week_start = week_start - timedelta(days=7)
                previous_result = await self.session.execute(
                    select(func.count(Master.id))
                    .where(
                        and_(
                            Master.created_at >= prev_week_start,
                            Master.created_at < week_start
                        )
                    )
                )
                previous_period = previous_result.scalar() or 0
            else:
                current_period = 0
                previous_period = 0
            
            # Calculate growth rate
            if previous_period > 0:
                growth_rate = ((current_period - previous_period) / previous_period) * 100
            else:
                growth_rate = 100.0 if current_period > 0 else 0.0
            
            # Calculate activation rate (onboarded / total registered)
            total_result = await self.session.execute(
                select(func.count(Master.id))
            )
            total_masters = total_result.scalar() or 0
            
            onboarded_result = await self.session.execute(
                select(func.count(Master.id))
                .where(Master.is_onboarded == True)
            )
            onboarded_masters = onboarded_result.scalar() or 0
            
            activation_rate = (
                (onboarded_masters / total_masters * 100)
                if total_masters > 0
                else 0.0
            )
            
            metrics = {
                "dau": dau,
                "wau": wau,
                "mau": mau,
                "growth_rate": round(growth_rate, 1),
                "activation_rate": round(activation_rate, 1),
                "period": period
            }
            
            logger.info(f"Growth metrics calculated: {metrics}")
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating growth metrics: {e}", exc_info=True)
            return {
                "dau": 0,
                "wau": 0,
                "mau": 0,
                "growth_rate": 0.0,
                "activation_rate": 0.0,
                "period": period
            }
