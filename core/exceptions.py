"""
Custom application exceptions.

These exceptions represent business logic errors that should be handled
gracefully with user-friendly messages.
"""
from typing import Optional


class BeautyAssistError(Exception):
    """Base exception for all application errors."""
    
    message: str = "Произошла ошибка"
    
    def __init__(self, message: Optional[str] = None, **kwargs):
        self.message = message or self.message
        self.details = kwargs
        super().__init__(self.message)


# ============== Authentication & Authorization ==============

class NotRegisteredError(BeautyAssistError):
    """User is not registered."""
    message = "Нажмите /start для регистрации"


class PermissionDeniedError(BeautyAssistError):
    """User doesn't have permission for this action."""
    message = "Доступ запрещён"


class AdminOnlyError(PermissionDeniedError):
    """Action is only allowed for administrators."""
    message = "Только для администраторов"


# ============== Subscription ==============

class SubscriptionError(BeautyAssistError):
    """Base subscription error."""
    message = "Ошибка подписки"


class SubscriptionExpiredError(SubscriptionError):
    """User's subscription has expired."""
    message = "Срок подписки истёк"


class TrialExpiredError(SubscriptionError):
    """User's trial period has expired."""
    message = "Пробный период завершён"


class LimitExceededError(SubscriptionError):
    """User has exceeded their subscription limits."""
    message = "Достигнут лимит тарифа"
    
    def __init__(
        self,
        resource: str,
        current: int,
        limit: int,
        message: Optional[str] = None
    ):
        self.resource = resource
        self.current = current
        self.limit = limit
        super().__init__(
            message or f"Достигнут лимит {resource}: {current}/{limit}"
        )


class ClientLimitExceededError(LimitExceededError):
    """Client limit exceeded."""
    def __init__(self, current: int, limit: int):
        super().__init__("клиентов", current, limit)


class AppointmentLimitExceededError(LimitExceededError):
    """Monthly appointment limit exceeded."""
    def __init__(self, current: int, limit: int):
        super().__init__("записей в месяц", current, limit)


class ServiceLimitExceededError(LimitExceededError):
    """Service limit exceeded."""
    def __init__(self, current: int, limit: int):
        super().__init__("услуг", current, limit)


# ============== Appointments ==============

class AppointmentError(BeautyAssistError):
    """Base appointment error."""
    message = "Ошибка записи"


class AppointmentNotFoundError(AppointmentError):
    """Appointment not found."""
    message = "Запись не найдена"
    
    def __init__(self, appointment_id: Optional[int] = None):
        self.appointment_id = appointment_id
        super().__init__(f"Запись #{appointment_id} не найдена" if appointment_id else self.message)


class AppointmentConflictError(AppointmentError):
    """Time slot is already taken."""
    message = "Выбранное время уже занято"
    
    def __init__(self, start_time: Optional[str] = None, end_time: Optional[str] = None):
        self.start_time = start_time
        self.end_time = end_time
        super().__init__()


class AppointmentStatusError(AppointmentError):
    """Invalid appointment status transition."""
    message = "Невозможно изменить статус записи"
    
    def __init__(self, current_status: str, target_status: str):
        self.current_status = current_status
        self.target_status = target_status
        super().__init__(
            f"Невозможно изменить статус с '{current_status}' на '{target_status}'"
        )


class PastAppointmentError(AppointmentError):
    """Cannot modify past appointments."""
    message = "Нельзя изменить прошедшую запись"


# ============== Services ==============

class ServiceError(BeautyAssistError):
    """Base service error."""
    message = "Ошибка услуги"


class ServiceNotFoundError(ServiceError):
    """Service not found."""
    message = "Услуга не найдена"


class ServiceInactiveError(ServiceError):
    """Service is not active."""
    message = "Услуга неактивна"


# ============== Clients ==============

class ClientError(BeautyAssistError):
    """Base client error."""
    message = "Ошибка клиента"


class ClientNotFoundError(ClientError):
    """Client not found."""
    message = "Клиент не найден"


class DuplicateClientError(ClientError):
    """Client with this phone already exists."""
    message = "Клиент с таким телефоном уже существует"


# ============== Payment ==============

class PaymentError(BeautyAssistError):
    """Base payment error."""
    message = "Ошибка оплаты"


class PaymentFailedError(PaymentError):
    """Payment failed."""
    message = "Оплата не прошла"
    
    def __init__(self, reason: Optional[str] = None):
        self.reason = reason
        super().__init__(f"Оплата не прошла: {reason}" if reason else self.message)


class PaymentCancelledError(PaymentError):
    """Payment was cancelled."""
    message = "Оплата отменена"


# ============== Validation ==============

class ValidationError(BeautyAssistError):
    """Data validation error."""
    message = "Ошибка валидации"
    
    def __init__(self, field: str, error: str):
        self.field = field
        self.error = error
        super().__init__(f"Ошибка в поле '{field}': {error}")


class InvalidTimeError(ValidationError):
    """Invalid time format."""
    def __init__(self, value: str):
        super().__init__("время", f"Неверный формат: {value}")


class InvalidPhoneError(ValidationError):
    """Invalid phone format."""
    def __init__(self, value: str):
        super().__init__("телефон", f"Неверный формат: {value}")


# ============== Rate Limiting ==============

class RateLimitError(BeautyAssistError):
    """Too many requests."""
    message = "Слишком много запросов. Подождите немного."
    
    def __init__(self, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        super().__init__()


# ============== External Services ==============

class ExternalServiceError(BeautyAssistError):
    """External service error."""
    message = "Сервис временно недоступен"


class TelegramError(ExternalServiceError):
    """Telegram API error."""
    message = "Ошибка Telegram API"


class SMSServiceError(ExternalServiceError):
    """SMS service error."""
    message = "Ошибка отправки SMS"
