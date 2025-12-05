"""
Handlers for YooKassa payments
"""
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from database.base import get_db
from database.repositories.subscription import SubscriptionRepository
from database.repositories.master import MasterRepository
from bot.subscription_plans import get_plan_config
from services.yookassa_service import yookassa_service
from bot.keyboards.subscription import get_subscription_keyboard
from bot.config import settings

logger = logging.getLogger(__name__)

router = Router(name='yookassa')


@router.callback_query(F.data.startswith("yookassa_pay:"))
async def process_yookassa_payment(callback: CallbackQuery, state: FSMContext):
    """Handle YooKassa payment button click."""
    try:
        await callback.answer()
        
        # Extract plan ID
        plan_id = callback.data.split(":")[1]
        plan = get_plan_config(plan_id)
        
        if not plan:
            await callback.message.answer("❌ Неверный тариф")
            return
        
        # Check if YooKassa is enabled
        if not yookassa_service.enabled:
            await callback.message.answer(
                "❌ Оплата через карты временно недоступна\n"
                "Используйте оплату через Telegram Stars"
            )
            return
        
        async with get_db() as session:
            master_repo = MasterRepository(session)
            sub_repo = SubscriptionRepository(session)
            
            # Get master
            master = await master_repo.get_by_telegram_id(callback.from_user.id)
            if not master:
                await callback.message.answer("❌ Пользователь не найден")
                return
            
            # Create pending subscription
            from datetime import datetime, timedelta
            subscription = await sub_repo.create_subscription(
                master_id=master.id,
                plan=plan.plan,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + plan.duration,
                amount=plan.price_rub,
                currency='RUB',
                payment_method=None  # Will be set after payment
            )
            
            # Create YooKassa payment
            return_url = settings.yookassa_return_url or "https://t.me/your_bot"
            payment_data = await yookassa_service.create_payment(
                amount=plan.price_rub,
                currency='RUB',
                description=f"Подписка {plan.name}",
                return_url=return_url,
                subscription_id=subscription.id,
                master_id=master.id,
                metadata={
                    'plan': plan_id,
                    'telegram_id': callback.from_user.id
                }
            )
            
            if not payment_data:
                await callback.message.answer(
                    "❌ Не удалось создать платеж\n"
                    "Попробуйте позже или используйте Telegram Stars"
                )
                return
            
            # Send payment link
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="💳 Оплатить",
                    url=payment_data['confirmation_url']
                )],
                [InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data="subscription_menu"
                )]
            ])
            
            await callback.message.edit_text(
                f"💳 <b>Оплата через карту/СБП</b>\n\n"
                f"📦 Тариф: {plan.name}\n"
                f"💰 Сумма: {plan.price_rub}₽\n\n"
                f"Нажмите кнопку ниже для оплаты.\n"
                f"После успешной оплаты подписка активируется автоматически.",
                reply_markup=keyboard
            )
            
            logger.info(
                f"YooKassa payment created for master {master.id}: "
                f"{payment_data['payment_id']}"
            )
            
    except Exception as e:
        logger.error(f"Error processing YooKassa payment: {e}", exc_info=True)
        await callback.message.answer(
            "❌ Произошла ошибка при создании платежа"
        )
