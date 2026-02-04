"""Subscription and payment related messages."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class SubscriptionMessages:
    """Messages for subscription management."""
    
    # Status
    SUBSCRIPTION_ACTIVE = "✅ Подписка активна"
    SUBSCRIPTION_EXPIRED = "❌ Подписка истекла"
    SUBSCRIPTION_TRIAL = "🎁 Пробный период"
    
    # Limits
    FREE_LIMIT_REACHED = "Достигнут лимит бесплатного тарифа"
    
    @staticmethod
    def subscription_status(
        is_premium: bool,
        is_trial: bool,
        trial_ends: Optional[datetime],
        subscription_ends: Optional[datetime]
    ) -> str:
        """Format subscription status message."""
        if is_premium:
            end_date = subscription_ends.strftime('%d.%m.%Y') if subscription_ends else "бессрочно"
            return (
                f"💎 <b>Premium подписка</b>\n\n"
                f"✅ Статус: Активна\n"
                f"📅 Действует до: {end_date}\n\n"
                f"Вам доступны все функции без ограничений!"
            )
        elif is_trial:
            end_date = trial_ends.strftime('%d.%m.%Y') if trial_ends else "скоро"
            return (
                f"🎁 <b>Пробный период</b>\n\n"
                f"📅 Действует до: {end_date}\n\n"
                f"Все функции доступны без ограничений.\n"
                f"После окончания пробного периода перейдёте на бесплатный тариф."
            )
        else:
            return (
                f"📋 <b>Бесплатный тариф</b>\n\n"
                f"Вам доступны базовые функции с ограничениями.\n\n"
                f"Оформите Premium для полного доступа!"
            )
    
    @staticmethod
    def limit_warning(resource: str, current: int, limit: int) -> str:
        """Warning when approaching limit."""
        return (
            f"⚠️ <b>Внимание!</b>\n\n"
            f"Вы используете {current} из {limit} {resource}.\n"
            f"При достижении лимита новые записи будут недоступны.\n\n"
            f"Оформите Premium для снятия ограничений!"
        )
    
    @staticmethod
    def payment_success(amount: int, end_date: str) -> str:
        """Successful payment message."""
        return (
            f"🎉 <b>Оплата прошла успешно!</b>\n\n"
            f"💰 Сумма: {amount} ₽\n"
            f"📅 Подписка активна до: {end_date}\n\n"
            f"Спасибо за доверие! Все Premium функции теперь доступны."
        )
    
    @staticmethod
    def payment_pending() -> str:
        """Payment pending message."""
        return (
            f"⏳ <b>Ожидание оплаты</b>\n\n"
            f"Пожалуйста, завершите оплату по ссылке выше.\n"
            f"После оплаты Premium будет активирован автоматически."
        )
    
    @staticmethod
    def payment_failed(reason: Optional[str] = None) -> str:
        """Payment failed message."""
        msg = "❌ <b>Ошибка оплаты</b>\n\n"
        if reason:
            msg += f"Причина: {reason}\n\n"
        msg += "Попробуйте повторить оплату или обратитесь в поддержку."
        return msg
