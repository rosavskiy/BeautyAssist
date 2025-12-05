"""
Error handler middleware for centralized exception handling.

Catches all unhandled exceptions and provides user-friendly error messages.
"""

import logging
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseMiddleware):
    """Handle all errors gracefully."""
    
    async def __call__(self, handler, event, data):
        """
        Catch and handle all exceptions.
        
        Args:
            handler: Next handler in chain
            event: Incoming event
            data: Additional data
        
        Returns:
            Handler result or None on error
        """
        try:
            return await handler(event, data)
        except Exception as e:
            logger.error(
                f"Unhandled error: {e}",
                exc_info=True,
                extra={
                    "user_id": event.from_user.id,
                    "event_type": type(event).__name__
                }
            )
            
            # Send user-friendly message
            try:
                if isinstance(event, Message):
                    await event.answer(
                        "❌ Произошла ошибка. Попробуйте позже или обратитесь в поддержку."
                    )
                elif isinstance(event, CallbackQuery):
                    await event.answer(
                        "❌ Произошла ошибка",
                        show_alert=True
                    )
            except Exception as send_error:
                logger.error(f"Failed to send error message: {send_error}")
            
            # Don't propagate exception
            return None
