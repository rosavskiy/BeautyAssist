"""
Middlewares package initialization.

This package contains all middleware components:
- logging.py: Request/response logging
- error_handler.py: Centralized error handling
- throttling.py: Rate limiting for bot commands
- auth.py: Master registration check
"""

from aiogram import Dispatcher


def setup_middlewares(dp: Dispatcher):
    """
    Setup all middlewares in the correct order.
    
    Order matters! Middlewares are executed in the order they are registered.
    
    Args:
        dp: Aiogram Dispatcher instance
    """
    from .logging import LoggingMiddleware
    from .error_handler import ErrorHandlerMiddleware
    from .throttling import ThrottlingMiddleware
    from .auth import AuthMiddleware
    from .subscription import SubscriptionMiddleware
    
    # Logging first to capture all events
    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())
    
    # Error handler to catch all exceptions
    dp.message.middleware(ErrorHandlerMiddleware())
    dp.callback_query.middleware(ErrorHandlerMiddleware())
    
    # Throttling to prevent spam
    dp.message.middleware(ThrottlingMiddleware())
    dp.callback_query.middleware(ThrottlingMiddleware())
    
    # Auth check (after rate limiting)
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    
    # Subscription check last (after auth)
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())


__all__ = ['setup_middlewares']
