"""Admin-only middleware."""
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message

from bot.config import settings


class AdminOnlyMiddleware(BaseMiddleware):
    """Middleware to restrict access to admin-only commands."""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Check if user is admin before allowing access."""
        
        # Only check for Message events (commands)
        if not isinstance(event, Message):
            return await handler(event, data)
        
        user_id = event.from_user.id if event.from_user else None
        
        # Check if user is in admin list
        if user_id not in settings.admin_telegram_ids:
            await event.answer(
                "❌ У вас нет доступа к административным командам.\n"
                "Эта функция доступна только создателю бота."
            )
            return
        
        # User is admin, proceed
        return await handler(event, data)
