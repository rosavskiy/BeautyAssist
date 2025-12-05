"""
Background tasks for sending reminders and checking incomplete appointments.
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database.base import async_session_maker
from services.notifications import send_due_reminders
from services.incomplete_checker import check_and_notify_incomplete

logger = logging.getLogger(__name__)

# Global scheduler instance
reminder_scheduler = AsyncIOScheduler(timezone="UTC")

# Will be injected during startup
bot = None


def inject_bot(bot_instance):
    """Inject bot instance for background tasks."""
    global bot
    bot = bot_instance


async def scan_and_send_reminders():
    """Background task to scan and send due reminders."""
    try:
        async with async_session_maker() as session:
            sent_count = await send_due_reminders(bot, session)
            if sent_count > 0:
                logger.info(f"Sent {sent_count} reminders")
    except Exception as e:
        logger.error(f"Error sending reminders: {e}", exc_info=True)


async def check_incomplete_appointments():
    """Background task to notify masters about incomplete appointments."""
    try:
        async with async_session_maker() as session:
            await check_and_notify_incomplete(bot, session)
    except Exception as e:
        logger.error(f"Error checking incomplete appointments: {e}", exc_info=True)


async def check_subscriptions():
    """Background task to check expiring subscriptions."""
    try:
        from services.subscription_monitor import check_subscriptions_task
        await check_subscriptions_task(bot)
    except Exception as e:
        logger.error(f"Error checking subscriptions: {e}", exc_info=True)


def start_reminder_scheduler():
    """Start the reminder scheduler. Runs every minute."""
    reminder_scheduler.add_job(
        scan_and_send_reminders,
        'interval',
        minutes=1,
        id='reminder_scanner',
        replace_existing=True
    )
    
    # Check incomplete appointments daily at 9:00 AM
    reminder_scheduler.add_job(
        check_incomplete_appointments,
        'cron',
        hour=9,
        minute=0,
        id='incomplete_checker',
        replace_existing=True
    )
    
    # Check expiring subscriptions every 6 hours
    reminder_scheduler.add_job(
        check_subscriptions,
        'interval',
        hours=6,
        id='subscription_checker',
        replace_existing=True
    )
    
    reminder_scheduler.start()
    logger.info("Reminder scheduler started")


def stop_reminder_scheduler():
    """Stop the reminder scheduler."""
    if reminder_scheduler.running:
        reminder_scheduler.shutdown()
        logger.info("Reminder scheduler stopped")
