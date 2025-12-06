"""Expense category enum for validation."""
import enum


class ExpenseCategory(str, enum.Enum):
    """Valid expense categories."""
    
    MATERIALS = "materials"
    RENT = "rent"
    ADVERTISING = "advertising"
    TRANSPORT = "transport"
    EDUCATION = "education"
    EQUIPMENT = "equipment"
    OTHER = "other"
    
    @classmethod
    def get_display_name(cls, category: str) -> str:
        """Get Russian display name for category."""
        names = {
            cls.MATERIALS.value: "💎 Материалы",
            cls.RENT.value: "🏢 Аренда",
            cls.ADVERTISING.value: "📢 Реклама",
            cls.TRANSPORT.value: "🚗 Транспорт",
            cls.EDUCATION.value: "📚 Обучение",
            cls.EQUIPMENT.value: "🔧 Оборудование",
            cls.OTHER.value: "📦 Другое",
        }
        return names.get(category, category)
    
    @classmethod
    def is_valid(cls, category: str) -> bool:
        """Check if category is valid."""
        try:
            cls(category)
            return True
        except ValueError:
            return False
    
    @classmethod
    def get_all_values(cls) -> list[str]:
        """Get list of all valid category values."""
        return [c.value for c in cls]
