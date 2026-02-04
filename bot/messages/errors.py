"""Error messages for user-facing error handling."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorMessages:
    """User-friendly error messages."""
    
    # General errors
    GENERIC_ERROR = "❌ Произошла ошибка. Попробуйте позже или обратитесь в поддержку."
    GENERIC_ERROR_SHORT = "❌ Произошла ошибка"
    
    # Data errors
    INVALID_DATA = "❌ Ошибка данных"
    INVALID_ID = "❌ Неверный ID"
    
    # Permission errors
    ACCESS_DENIED = "❌ Доступ запрещён"
    ADMIN_ONLY = "❌ Только для администраторов"
    
    # Business logic errors
    APPOINTMENT_CONFLICT = "❌ Выбранное время уже занято"
    SERVICE_NOT_AVAILABLE = "❌ Услуга недоступна"
    CLIENT_LIMIT_REACHED = "❌ Достигнут лимит клиентов"
    
    # Rate limiting
    TOO_MANY_REQUESTS = "⏳ Слишком много запросов. Подождите немного."
    
    # Network/Technical
    SERVICE_UNAVAILABLE = "🔧 Сервис временно недоступен. Попробуйте позже."
    TIMEOUT_ERROR = "⏱ Время ожидания истекло. Попробуйте снова."
    
    @staticmethod
    def validation_error(field: str, message: str) -> str:
        """Format validation error."""
        return f"❌ Ошибка в поле «{field}»: {message}"
    
    @staticmethod
    def not_found(entity: str) -> str:
        """Format not found error."""
        return f"❌ {entity} не найден(а)"
    
    @staticmethod
    def limit_exceeded(resource: str, limit: int) -> str:
        """Format limit exceeded error."""
        return f"❌ Превышен лимит {resource} (максимум: {limit})"
