"""Middleware to check subscription status."""
import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from database.base import DBSession
from database.repositories.subscription import SubscriptionRepository
from database.repositories.master import MasterRepository

logger = logging.getLogger(__name__)

# Commands that don't require active subscription
ALLOWED_COMMANDS = {
    '/start',
    '/subscription',
    '/help',
}

# Callback data patterns that don't require subscription
ALLOWED_CALLBACKS = {
    'subscription:',  # All subscription-related callbacks
    'setup_city:',    # Onboarding: city selection
    'setup_schedule:', # Onboarding: schedule setup
    'setup_service:',  # Onboarding: service management
}


class SubscriptionMiddleware(BaseMiddleware):
    """Middleware to check if user has active subscription."""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Check subscription before processing update."""
        # Only check for messages and callback queries
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)
        
        # Get user telegram ID
        if isinstance(event, Message):
            user_id = event.from_user.id
            text = event.text or ""
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            text = event.data or ""
        else:
            return await handler(event, data)
        
        # Check if command/callback is allowed without subscription
        if isinstance(event, Message):
            # Check if it's an allowed command
            if any(text.startswith(cmd) for cmd in ALLOWED_COMMANDS):
                return await handler(event, data)
        
        if isinstance(event, CallbackQuery):
            # Check if it's an allowed callback
            if any(text.startswith(pattern) for pattern in ALLOWED_CALLBACKS):
                return await handler(event, data)
        
        # Check subscription
        try:
            async with DBSession() as session:
                master_repo = MasterRepository(session)
                master = await master_repo.get_by_telegram_id(user_id)
                
                if not master:
                    # User not registered yet, allow /start to pass through
                    if isinstance(event, Message) and text.startswith('/start'):
                        return await handler(event, data)
                    return
                
                repo = SubscriptionRepository(session)
                has_access = await repo.check_access(master.id)
                
                if not has_access:
                    # No active subscription
                    if isinstance(event, Message):
                        await event.answer(
                            "❌ <b>Подписка неактивна</b>\n\n"
                            "Для использования бота необходима активная подписка.\n\n"
                            "Используйте /subscription для активации.",
                        )
                    elif isinstance(event, CallbackQuery):
                        await event.answer(
                            "Подписка неактивна. Используйте /subscription",
                            show_alert=True,
                        )
                    return
                
                # Has active subscription, proceed
                return await handler(event, data)
                
        except Exception as e:
            logger.error(f"Error in subscription middleware: {e}", exc_info=True)
            # On error, allow request to proceed (fail-open for reliability)
            return await handler(event, data)
