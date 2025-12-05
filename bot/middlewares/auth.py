"""
Authentication middleware to check master registration.

Ensures that only registered masters can access protected commands.
"""

import logging
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from database import async_session_maker
from database.repositories import MasterRepository

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    """Check if user is registered master for protected commands."""
    
    # Commands that don't require authentication
    ALLOWED_COMMANDS = {'/start', '/admin'}
    
    # Callback patterns that don't require authentication
    ALLOWED_CALLBACK_PREFIXES = {'city:', 'client_confirm:', 'client_cancel'}
    
    async def __call__(self, handler, event, data):
        """
        Check authentication before processing event.
        
        Args:
            handler: Next handler in chain
            event: Incoming event
            data: Additional data
        
        Returns:
            Handler result or None if not authenticated
        """
        # Check if this is an allowed command
        if isinstance(event, Message) and event.text:
            # Check exact match or command with parameters (e.g., /start code)
            if event.text in self.ALLOWED_COMMANDS or any(event.text.startswith(cmd + ' ') for cmd in self.ALLOWED_COMMANDS):
                return await handler(event, data)
        
        # Check if this is an allowed callback
        if isinstance(event, CallbackQuery) and event.data:
            for prefix in self.ALLOWED_CALLBACK_PREFIXES:
                if event.data.startswith(prefix):
                    return await handler(event, data)
        
        # Check if master exists
        user_id = event.from_user.id
        try:
            async with async_session_maker() as session:
                mrepo = MasterRepository(session)
                master = await mrepo.get_by_telegram_id(user_id)
                
                if not master:
                    logger.info(
                        f"Unregistered user {user_id} attempted to use bot",
                        extra={"user_id": user_id}
                    )
                    
                    # Not a registered master
                    if isinstance(event, Message):
                        await event.answer(
                            "❌ Сначала зарегистрируйтесь через /start"
                        )
                    elif isinstance(event, CallbackQuery):
                        await event.answer(
                            "❌ Сначала зарегистрируйтесь",
                            show_alert=True
                        )
                    return None
                
                # Add master to data for handlers
                data["master"] = master
                logger.debug(
                    f"Authenticated master {master.id}",
                    extra={"master_id": master.id, "user_id": user_id}
                )
        except Exception as e:
            logger.error(f"Auth error: {e}", exc_info=True)
            # On error, block request
            return None
        
        return await handler(event, data)
