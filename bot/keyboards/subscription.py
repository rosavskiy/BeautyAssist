"""Keyboards for subscription management."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models.subscription import SubscriptionPlan


def get_subscription_menu_keyboard() -> InlineKeyboardMarkup:
    """Get main subscription menu keyboard."""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="🔙 Назад", callback_data="subscription:back")
    
    return builder.as_markup()


def get_subscription_actions_keyboard(
    has_subscription: bool,
    trial_available: bool = False,
    auto_renew: bool = False,
) -> InlineKeyboardMarkup:
    """Get subscription actions keyboard."""
    builder = InlineKeyboardBuilder()
    
    if has_subscription:
        # Has active subscription
        builder.button(text="📜 История подписок", callback_data="subscription:history")
        builder.button(text="💎 Продлить подписку", callback_data="subscription:choose_plan")
        
        if auto_renew:
            builder.button(text="🔴 Отключить автопродление", callback_data="subscription:toggle_renew")
        else:
            builder.button(text="🟢 Включить автопродление", callback_data="subscription:toggle_renew")
        
        builder.adjust(1)
    else:
        # No active subscription
        if trial_available:
            builder.button(text="🎁 Активировать пробный период", callback_data="subscription:activate_trial")
        
        builder.button(text="💎 Выбрать тариф", callback_data="subscription:choose_plan")
        builder.button(text="📜 История подписок", callback_data="subscription:history")
        builder.adjust(1)
    
    return builder.as_markup()


def get_plans_keyboard() -> InlineKeyboardMarkup:
    """Get subscription plans keyboard."""
    builder = InlineKeyboardBuilder()
    
    # Monthly
    builder.button(
        text="📅 1 месяц - 990₽",
        callback_data=f"subscription:buy:{SubscriptionPlan.MONTHLY.value}"
    )
    
    # Quarterly
    builder.button(
        text="📅 3 месяца - 2490₽ (скидка 15%)",
        callback_data=f"subscription:buy:{SubscriptionPlan.QUARTERLY.value}"
    )
    
    # Yearly
    builder.button(
        text="📅 12 месяцев - 8280₽ (скидка 30%)",
        callback_data=f"subscription:buy:{SubscriptionPlan.YEARLY.value}"
    )
    
    # Promo code button
    builder.button(text="🎫 У меня промокод", callback_data="subscription:promo_code")
    
    # Back button
    builder.button(text="🔙 Назад", callback_data="subscription:back")
    
    builder.adjust(1)
    return builder.as_markup()


def get_plan_detail_keyboard(plan: SubscriptionPlan) -> InlineKeyboardMarkup:
    """Get plan detail keyboard."""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="💳 Оплатить",
        callback_data=f"subscription:buy:{plan.value}"
    )
    builder.button(
        text="🔙 К выбору тарифов",
        callback_data="subscription:choose_plan"
    )
    
    builder.adjust(1)
    return builder.as_markup()
