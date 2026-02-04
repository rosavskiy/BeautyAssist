"""
Error handler middleware for centralized exception handling.

Catches all unhandled exceptions and provides user-friendly error messages.
Handles custom business exceptions with appropriate responses.
"""

import logging
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from core.exceptions import (
    BeautyAssistError,
    NotRegisteredError,
    PermissionDeniedError,
    AdminOnlyError,
    SubscriptionError,
    SubscriptionExpiredError,
    TrialExpiredError,
    LimitExceededError,
    AppointmentError,
    AppointmentNotFoundError,
    AppointmentConflictError,
    ServiceError,
    ClientError,
    PaymentError,
    ValidationError,
    RateLimitError,
    ExternalServiceError,
)
from bot.messages import ErrorMessages

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseMiddleware):
    """Handle all errors gracefully with business exception support."""
    
    # Map exception types to (message, show_alert) tuples
    EXCEPTION_HANDLERS = {
        # Registration
        NotRegisteredError: ("Нажмите /start для регистрации", True),
        
        # Permissions
        AdminOnlyError: (ErrorMessages.ADMIN_ONLY, True),
        PermissionDeniedError: (ErrorMessages.ACCESS_DENIED, True),
        
        # Rate limiting
        RateLimitError: (ErrorMessages.TOO_MANY_REQUESTS, True),
        
        # External services
        ExternalServiceError: (ErrorMessages.SERVICE_UNAVAILABLE, True),
    }
    
    async def __call__(self, handler, event, data):
        """
        Catch and handle all exceptions.
        
        Handles business exceptions with specific messages,
        and generic exceptions with a fallback error message.
        
        Args:
            handler: Next handler in chain
            event: Incoming event
            data: Additional data
        
        Returns:
            Handler result or None on error
        """
        try:
            return await handler(event, data)
        
        except BeautyAssistError as e:
            # Handle business exceptions with appropriate messages
            await self._handle_business_error(event, e)
            return None
        
        except Exception as e:
            # Handle unexpected exceptions
            logger.error(
                f"Unhandled error: {e}",
                exc_info=True,
                extra={
                    "user_id": getattr(event.from_user, 'id', None),
                    "event_type": type(event).__name__
                }
            )
            
            await self._send_error_message(
                event,
                ErrorMessages.GENERIC_ERROR,
                ErrorMessages.GENERIC_ERROR_SHORT,
                show_alert=True
            )
            return None
    
    async def _handle_business_error(self, event, error: BeautyAssistError):
        """Handle business logic exceptions."""
        error_type = type(error)
        
        # Check if we have a specific handler for this exception type
        if error_type in self.EXCEPTION_HANDLERS:
            message, show_alert = self.EXCEPTION_HANDLERS[error_type]
            await self._send_error_message(event, message, message, show_alert)
            return
        
        # Handle exception hierarchies with specific logic
        if isinstance(error, LimitExceededError):
            message = f"❌ Достигнут лимит {error.resource}: {error.current}/{error.limit}"
            await self._send_error_message(event, message, message, show_alert=True)
            
        elif isinstance(error, (SubscriptionExpiredError, TrialExpiredError)):
            message = f"💎 {error.message}. Оформите Premium для продолжения."
            await self._send_error_message(event, message, error.message, show_alert=True)
            
        elif isinstance(error, SubscriptionError):
            await self._send_error_message(event, error.message, error.message, show_alert=True)
            
        elif isinstance(error, AppointmentConflictError):
            await self._send_error_message(
                event, 
                ErrorMessages.APPOINTMENT_CONFLICT,
                ErrorMessages.APPOINTMENT_CONFLICT,
                show_alert=True
            )
            
        elif isinstance(error, (AppointmentNotFoundError, AppointmentError)):
            await self._send_error_message(event, error.message, error.message, show_alert=True)
            
        elif isinstance(error, ValidationError):
            message = f"❌ Ошибка в поле «{error.field}»: {error.error}"
            await self._send_error_message(event, message, ErrorMessages.INVALID_DATA, show_alert=True)
            
        elif isinstance(error, (ServiceError, ClientError)):
            await self._send_error_message(event, error.message, error.message, show_alert=True)
            
        elif isinstance(error, PaymentError):
            await self._send_error_message(event, error.message, error.message, show_alert=True)
            
        else:
            # Fallback for any other BeautyAssistError
            logger.warning(f"Unhandled business error: {error_type.__name__}: {error.message}")
            await self._send_error_message(
                event, 
                error.message, 
                ErrorMessages.GENERIC_ERROR_SHORT,
                show_alert=True
            )
    
    async def _send_error_message(
        self,
        event,
        message_text: str,
        callback_text: str,
        show_alert: bool = False
    ):
        """Send error message to user based on event type."""
        try:
            if isinstance(event, Message):
                await event.answer(f"❌ {message_text}")
            elif isinstance(event, CallbackQuery):
                await event.answer(callback_text, show_alert=show_alert)
        except Exception as send_error:
            logger.error(f"Failed to send error message: {send_error}")
