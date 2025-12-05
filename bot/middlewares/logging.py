"""
Logging middleware for request/response tracking.

Logs all incoming updates with timing information.
"""

import logging
import time
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """Log all incoming updates with timing."""
    
    async def __call__(self, handler, event, data):
        """
        Log incoming event and execution time.
        
        Args:
            handler: Next handler in chain
            event: Incoming event (Message, CallbackQuery, etc.)
            data: Additional data
        
        Returns:
            Handler result
        """
        start_time = time.time()
        
        # Log incoming event
        if isinstance(event, Message):
            user_id = event.from_user.id
            username = event.from_user.username or "N/A"
            text = event.text[:50] if event.text else "N/A"
            logger.info(
                f"Message from {user_id} (@{username}): {text}",
                extra={"user_id": user_id, "username": username}
            )
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            username = event.from_user.username or "N/A"
            logger.info(
                f"Callback from {user_id} (@{username}): {event.data}",
                extra={"user_id": user_id, "username": username, "callback_data": event.data}
            )
        
        try:
            result = await handler(event, data)
            duration = time.time() - start_time
            logger.info(
                f"Handled in {duration:.2f}s",
                extra={"duration": duration}
            )
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Error after {duration:.2f}s: {e}",
                exc_info=True,
                extra={"duration": duration}
            )
            raise
