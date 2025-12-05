"""Admin keyboards for navigation."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_admin_main_menu() -> InlineKeyboardMarkup:
    """Get main admin menu keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Dashboard", callback_data="admin:dashboard"),
        ],
        [
            InlineKeyboardButton(text="👥 Мастера", callback_data="admin:masters"),
            InlineKeyboardButton(text="📣 Рассылка", callback_data="admin:broadcast"),
        ],
        [
            InlineKeyboardButton(text="🎫 Промокоды", callback_data="admin:promo_codes"),
            InlineKeyboardButton(text="💰 Платежи", callback_data="admin:payments"),
        ],
        [
            InlineKeyboardButton(text="📈 Аналитика", callback_data="admin:analytics"),
        ],
    ])
    return keyboard


def get_masters_keyboard(page: int = 0, has_next: bool = False) -> InlineKeyboardMarkup:
    """Get masters list navigation keyboard.
    
    Args:
        page: Current page number
        has_next: Whether there are more pages
    """
    buttons = []
    
    # Filters row
    buttons.append([
        InlineKeyboardButton(text="✅ Прошли онбординг", callback_data="admin:masters:filter:onboarded"),
        InlineKeyboardButton(text="⭐ Premium", callback_data="admin:masters:filter:premium"),
    ])
    
    # Navigation row
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin:masters:page:{page-1}"))
    if has_next:
        nav_row.append(InlineKeyboardButton(text="➡️ Далее", callback_data=f"admin:masters:page:{page+1}"))
    
    if nav_row:
        buttons.append(nav_row)
    
    # Back button
    buttons.append([
        InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin:menu"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_broadcast_keyboard() -> InlineKeyboardMarkup:
    """Get broadcast menu keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📤 Новая рассылка", callback_data="admin:broadcast:new"),
        ],
        [
            InlineKeyboardButton(text="📜 История рассылок", callback_data="admin:broadcast:history"),
        ],
        [
            InlineKeyboardButton(text="🔙 Главное меню", callback_data="admin:menu"),
        ],
    ])
    return keyboard


def get_broadcast_confirm_keyboard(broadcast_id: int | None = None) -> InlineKeyboardMarkup:
    """Get broadcast confirmation keyboard.
    
    Args:
        broadcast_id: Broadcast ID for confirmation
    """
    if broadcast_id:
        confirm_data = f"admin:broadcast:confirm:{broadcast_id}"
    else:
        confirm_data = "admin:broadcast:confirm"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправить всем", callback_data=confirm_data),
        ],
        [
            InlineKeyboardButton(text="❌ Отменить", callback_data="admin:broadcast"),
        ],
    ])
    return keyboard


def get_master_detail_keyboard(master_id: int, page: int = 0) -> InlineKeyboardMarkup:
    """Get master detail actions keyboard.
    
    Args:
        master_id: Master ID
        page: Page number to return to
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📊 Статистика", 
                callback_data=f"admin:master:stats:{master_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="💬 Написать", 
                callback_data=f"admin:master:message:{master_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔙 К списку", 
                callback_data=f"admin:masters:page:{page}"
            ),
        ],
    ])
    return keyboard


def get_promo_codes_menu() -> InlineKeyboardMarkup:
    """Get promo codes management menu."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Список промокодов", callback_data="admin:promo:list"),
        ],
        [
            InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin:promo:create"),
        ],
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin:promo:stats"),
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="admin:menu"),
        ],
    ])
    return keyboard


def get_promo_code_detail_keyboard(code: str) -> InlineKeyboardMarkup:
    """Get promo code detail keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔴 Деактивировать" if True else "🟢 Активировать",
                callback_data=f"admin:promo:toggle:{code}"
            ),
        ],
        [
            InlineKeyboardButton(text="🔙 К списку", callback_data="admin:promo:list"),
        ],
    ])
    return keyboard
