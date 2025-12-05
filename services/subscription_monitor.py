"""Subscription monitoring and auto-renewal service."""
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from database.base import get_db
from database.repositories.subscription import SubscriptionRepository
from database.repositories.master import MasterRepository
from database.models.subscription import SubscriptionStatus
from bot.subscription_plans import get_plan_config, SubscriptionPlan

logger = logging.getLogger(__name__)


class SubscriptionMonitorService:
    """Service for monitoring subscriptions and sending reminders."""
    
    def __init__(self, bot: Bot):
        self.bot = bot
    
    async def check_expiring_subscriptions(self):
        """Check for expiring subscriptions and send reminders."""
        logger.info("Checking expiring subscriptions...")
        
        async with get_db() as session:
            repo = SubscriptionRepository(session)
            master_repo = MasterRepository(session)
            
            # Check subscriptions expiring in 3 days
            three_days_subs = await repo.get_expiring_soon(days=3)
            for sub in three_days_subs:
                # Check if reminder was already sent
                if not hasattr(sub, '_reminder_3d_sent'):
                    await self._send_expiry_reminder(sub, master_repo, days_left=3)
            
            # Check subscriptions expiring in 1 day
            one_day_subs = await repo.get_expiring_soon(days=1)
            for sub in one_day_subs:
                if not hasattr(sub, '_reminder_1d_sent'):
                    await self._send_expiry_reminder(sub, master_repo, days_left=1)
            
            # Check already expired subscriptions
            expired_subs = await repo.get_expired_subscriptions(limit=50)
            for sub in expired_subs:
                await self._expire_subscription(sub, repo, master_repo)
            
            logger.info(
                f"Checked subscriptions: "
                f"{len(three_days_subs)} expiring in 3d, "
                f"{len(one_day_subs)} expiring in 1d, "
                f"{len(expired_subs)} expired"
            )
    
    async def _send_expiry_reminder(
        self,
        subscription,
        master_repo: MasterRepository,
        days_left: int,
    ):
        """Send expiry reminder to master."""
        try:
            master = await master_repo.get_by_id(subscription.master_id)
            if not master:
                return
            
            plan_config = get_plan_config(SubscriptionPlan(subscription.plan))
            
            if days_left == 3:
                text = (
                    f"⚠️ <b>Подписка истекает через 3 дня</b>\n\n"
                    f"Ваша подписка «{plan_config.name}» истекает "
                    f"{subscription.end_date.strftime('%d.%m.%Y')}.\n\n"
                    f"Продлите подписку, чтобы не потерять доступ к боту.\n\n"
                    f"Используйте /subscription для продления."
                )
            else:  # 1 day
                text = (
                    f"🔴 <b>Подписка истекает завтра!</b>\n\n"
                    f"Ваша подписка «{plan_config.name}» истекает завтра, "
                    f"{subscription.end_date.strftime('%d.%m.%Y')}.\n\n"
                    f"⚠️ После истечения доступ к боту будет заблокирован.\n\n"
                    f"Продлите прямо сейчас: /subscription"
                )
            
            await self.bot.send_message(
                chat_id=master.telegram_id,
                text=text,
            )
            
            logger.info(
                f"Sent {days_left}d expiry reminder to master {master.id} "
                f"(subscription {subscription.id})"
            )
            
        except Exception as e:
            logger.error(f"Error sending expiry reminder: {e}", exc_info=True)
    
    async def _expire_subscription(
        self,
        subscription,
        repo: SubscriptionRepository,
        master_repo: MasterRepository,
    ):
        """Expire subscription and update master status."""
        try:
            # Update subscription status
            await repo.expire_subscription(subscription.id)
            
            # Update master
            master = await master_repo.get_by_id(subscription.master_id)
            if master:
                master.is_premium = False
                master.premium_until = None
            
            # Send notification
            if master:
                text = (
                    "❌ <b>Подписка истекла</b>\n\n"
                    "Ваша подписка на BeautyAssist истекла.\n\n"
                    "Для продолжения работы с ботом продлите подписку: /subscription"
                )
                
                try:
                    await self.bot.send_message(
                        chat_id=master.telegram_id,
                        text=text,
                    )
                except Exception as e:
                    logger.error(f"Error sending expiry notification: {e}")
            
            logger.info(f"Expired subscription {subscription.id} for master {subscription.master_id}")
            
        except Exception as e:
            logger.error(f"Error expiring subscription: {e}", exc_info=True)


async def check_subscriptions_task(bot: Bot):
    """Background task to check subscriptions."""
    service = SubscriptionMonitorService(bot)
    await service.check_expiring_subscriptions()
