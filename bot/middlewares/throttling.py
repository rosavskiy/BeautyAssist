"""
Throttling middleware for rate limiting bot commands.

Prevents spam by limiting the number of requests per user.
"""

import logging
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
import redis.asyncio as redis
from bot.config import settings

logger = logging.getLogger(__name__)


class ThrottlingMiddleware(BaseMiddleware):
    """Rate limiting middleware using Redis."""
    
    def __init__(self):
        """Initialize throttling middleware."""
        self.redis = None
        self.redis_available = False
        try:
            self.redis = redis.from_url(settings.redis_url)
            # Will test connection on first use
            self.redis_available = True
        except Exception as e:
            logger.warning(f"Redis not available for throttling: {e}")
    
    async def __call__(self, handler, event, data):
        """
        Check rate limit before processing event.
        
        Limit: 5 requests per minute per user
        
        Args:
            handler: Next handler in chain
            event: Incoming event
            data: Additional data
        
        Returns:
            Handler result or None if rate limit exceeded
        """
        # Skip throttling if Redis not available
        if not self.redis_available:
            return await handler(event, data)
        
        user_id = event.from_user.id
        
        # Skip throttling for admins
        if user_id in settings.admin_telegram_ids:
            return await handler(event, data)
        
        key = f"throttle:bot:{user_id}"
        
        try:
            # Check rate limit (15 requests per minute)
            count = await self.redis.get(key)
            if count and int(count) >= 15:
                logger.warning(
                    f"Rate limit exceeded for user {user_id}",
                    extra={"user_id": user_id}
                )
                
                # Send warning only once
                warning_key = f"throttle:warned:{user_id}"
                warned = await self.redis.get(warning_key)
                if not warned:
                    if isinstance(event, Message):
                        await event.answer("⚠️ Слишком много запросов. Подождите минуту.")
                    elif isinstance(event, CallbackQuery):
                        await event.answer("⚠️ Слишком много запросов", show_alert=True)
                    
                    # Mark as warned for 60 seconds
                    await self.redis.setex(warning_key, 60, "1")
                
                return None
            
            # Increment counter
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, 60)  # 1 minute
            await pipe.execute()
        except Exception as e:
            # If Redis error occurs, disable throttling and continue
            logger.warning(f"Redis error in throttling, disabling: {e}")
            self.redis_available = False
        
        return await handler(event, data)
