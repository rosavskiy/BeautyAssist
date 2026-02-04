"""Handlers for subscription management."""
import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, PreCheckoutQuery, ContentType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.base import DBSession
from database.repositories.subscription import SubscriptionRepository
from database.repositories.master import MasterRepository
from database.models.subscription import SubscriptionPlan
from bot.subscription_plans import get_plan_config, format_plan_info, get_available_plans
from bot.keyboards.subscription import (
    get_subscription_menu_keyboard,
    get_plans_keyboard,
    get_subscription_actions_keyboard,
)
from services.payment import PaymentService

logger = logging.getLogger(__name__)

router = Router(name="subscription")


class PromoCodeStates(StatesGroup):
    """States for promo code input."""
    waiting_for_code = State()


@router.message(Command("subscription"))
async def cmd_subscription(message: Message):
    """Show subscription status and options."""
    async with DBSession() as session:
        repo = SubscriptionRepository(session)
        master_repo = MasterRepository(session)
        
        master = await master_repo.get_by_telegram_id(message.from_user.id)
        if not master:
            await message.answer("❌ Вы не зарегистрированы. Используйте /start")
            return
        
        # Get active subscription
        subscription = await repo.get_active_subscription(master.id)
        
        if subscription:
            plan_config = get_plan_config(SubscriptionPlan(subscription.plan))
            days_left = subscription.days_remaining
            
            text = "📋 <b>Ваша подписка</b>\n\n"
            text += f"📦 Тариф: {plan_config.name}\n"
            text += f"📅 Действует до: {subscription.end_date.strftime('%d.%m.%Y')}\n"
            text += f"⏳ Осталось дней: {days_left}\n\n"
            
            if subscription.auto_renew:
                text += "🔄 Автопродление: включено\n"
            else:
                text += "🔄 Автопродление: выключено\n"
            
            keyboard = get_subscription_actions_keyboard(
                has_subscription=True,
                auto_renew=subscription.auto_renew,
            )
        else:
            # Check if trial is available
            trial_available = await repo.is_trial_available(master.id)
            
            text = "❌ <b>У вас нет активной подписки</b>\n\n"
            text += "Для использования бота необходима подписка.\n\n"
            
            if trial_available:
                text += "🎁 Доступен пробный период на 30 дней!\n"
            
            keyboard = get_subscription_actions_keyboard(
                has_subscription=False,
                trial_available=trial_available,
            )
        
        await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "subscription:activate_trial")
async def activate_trial(call: CallbackQuery, bot):
    """Activate trial subscription."""
    async with DBSession() as session:
        repo = SubscriptionRepository(session)
        master_repo = MasterRepository(session)
        
        master = await master_repo.get_by_telegram_id(call.from_user.id)
        if not master:
            await call.answer("Ошибка: мастер не найден", show_alert=True)
            return
        
        # Check if trial is available
        if not await repo.is_trial_available(master.id):
            await call.answer("Пробный период уже был использован", show_alert=True)
            return
        
        # Activate trial
        payment_service = PaymentService(bot)
        success = await payment_service.activate_trial(
            master_id=master.id,
            telegram_id=call.from_user.id,
            session=session,
        )
        
        if success:
            await call.message.edit_text(
                "🎉 <b>Пробный период активирован!</b>\n\n"
                "✅ У вас есть 30 дней бесплатного доступа ко всем функциям бота.\n\n"
                "За 3 дня до окончания мы напомним о продлении подписки.",
            )
            await call.answer("Пробный период активирован!")
        else:
            await call.answer("Ошибка активации. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "subscription:choose_plan")
async def choose_plan(call: CallbackQuery):
    """Show available subscription plans."""
    plans = get_available_plans(exclude_trial=True)
    
    text = "💎 <b>Выберите тариф</b>\n\n"
    
    for plan_config in plans:
        text += format_plan_info(plan_config.plan)
        text += "\n➖➖➖➖➖➖➖➖➖➖\n\n"
    
    keyboard = get_plans_keyboard()
    await call.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("subscription:buy:"))
async def buy_subscription(call: CallbackQuery, bot):
    """Initiate payment for subscription."""
    plan_str = call.data.split(":")[-1]
    
    try:
        plan = SubscriptionPlan(plan_str)
    except ValueError:
        await call.answer("Неверный тариф", show_alert=True)
        return
    
    async with DBSession() as session:
        payment_service = PaymentService(bot)
        
        try:
            await payment_service.send_invoice(
                chat_id=call.from_user.id,
                plan=plan,
                session=session,
            )
            await call.answer("Счёт отправлен! Проверьте сообщения ниже.")
        except Exception as e:
            logger.error(f"Error sending invoice: {e}", exc_info=True)
            await call.answer("Ошибка создания счёта. Попробуйте позже.", show_alert=True)


@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    """Process pre-checkout query."""
    async with DBSession() as session:
        from bot.main import bot
        payment_service = PaymentService(bot)
        await payment_service.handle_pre_checkout(pre_checkout_query, session)


@router.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def process_successful_payment(message: Message, bot):
    """Process successful payment."""
    async with DBSession() as session:
        payment_service = PaymentService(bot)
        success = await payment_service.handle_successful_payment(
            payment=message.successful_payment,
            user_telegram_id=message.from_user.id,
            session=session,
        )
        
        if success:
            # Reward referrer if this is first payment
            from services.referral import ReferralService
            from database.repositories import MasterRepository
            
            master_repo = MasterRepository(session)
            master = await master_repo.get_by_telegram_id(message.from_user.id)
            
            if master:
                referral_service = ReferralService(session)
                result = await referral_service.activate_referral(
                    referred_id=master.id,
                    bot=bot
                )
                if result and result.get('success'):
                    logger.info(f"Referral reward processed for master {master.id}")
            
            subscription_text = "🎉 <b>Оплата прошла успешно!</b>\n\n"
            subscription_text += "✅ Ваша подписка активирована.\n"
            subscription_text += "Теперь у вас есть полный доступ ко всем функциям бота.\n\n"
            subscription_text += "Используйте /subscription для управления подпиской."
            
            await message.answer(subscription_text)
        else:
            await message.answer(
                "❌ Произошла ошибка при активации подписки.\n"
                "Пожалуйста, обратитесь в поддержку."
            )


@router.callback_query(F.data == "subscription:history")
async def subscription_history(call: CallbackQuery):
    """Show subscription history."""
    async with DBSession() as session:
        repo = SubscriptionRepository(session)
        master_repo = MasterRepository(session)
        
        master = await master_repo.get_by_telegram_id(call.from_user.id)
        if not master:
            await call.answer("Ошибка: мастер не найден", show_alert=True)
            return
        
        subscriptions = await repo.get_master_subscriptions(master.id, limit=5)
        
        if not subscriptions:
            text = "📋 <b>История подписок</b>\n\n"
            text += "У вас пока нет подписок."
        else:
            text = "📋 <b>История подписок</b>\n\n"
            
            for sub in subscriptions:
                plan_config = get_plan_config(SubscriptionPlan(sub.plan))
                status_emoji = "✅" if sub.status == "active" else "❌"
                
                text += f"{status_emoji} {plan_config.name}\n"
                text += f"  📅 {sub.start_date.strftime('%d.%m.%Y')} - {sub.end_date.strftime('%d.%m.%Y')}\n"
                text += f"  💰 {sub.amount} {sub.currency}\n"
                text += f"  📊 Статус: {sub.status}\n\n"
        
        await call.message.edit_text(text, reply_markup=get_subscription_menu_keyboard())


@router.callback_query(F.data == "subscription:back")
async def back_to_menu(call: CallbackQuery):
    """Return to subscription menu."""
    async with DBSession() as session:
        repo = SubscriptionRepository(session)
        master_repo = MasterRepository(session)
        
        master = await master_repo.get_by_telegram_id(call.from_user.id)
        if not master:
            await call.answer("Ошибка: мастер не найден", show_alert=True)
            return
        
        # Get active subscription
        subscription = await repo.get_active_subscription(master.id)
        
        if subscription:
            plan_config = get_plan_config(SubscriptionPlan(subscription.plan))
            days_left = subscription.days_remaining
            
            text = "📋 <b>Ваша подписка</b>\n\n"
            text += f"📦 Тариф: {plan_config.name}\n"
            text += f"📅 Действует до: {subscription.end_date.strftime('%d.%m.%Y')}\n"
            text += f"⏳ Осталось дней: {days_left}\n\n"
            
            if subscription.auto_renew:
                text += "🔄 Автопродление: включено\n"
            else:
                text += "🔄 Автопродление: выключено\n"
            
            keyboard = get_subscription_actions_keyboard(
                has_subscription=True,
                auto_renew=subscription.auto_renew,
            )
        else:
            # Check if trial is available
            trial_available = await repo.is_trial_available(master.id)
            
            text = "❌ <b>У вас нет активной подписки</b>\n\n"
            text += "Для использования бота необходима подписка.\n\n"
            
            if trial_available:
                text += "🎁 Доступен пробный период на 30 дней!\n"
            
            keyboard = get_subscription_actions_keyboard(
                has_subscription=False,
                trial_available=trial_available,
            )
        
        await call.message.edit_text(text, reply_markup=keyboard)
        await call.answer()


@router.callback_query(F.data == "subscription:promo_code")
async def enter_promo_code(call: CallbackQuery, state: FSMContext):
    """Start promo code input process."""
    await state.set_state(PromoCodeStates.waiting_for_code)
    
    text = (
        "🎫 <b>Введите промокод</b>\n\n"
        "Отправьте код одним сообщением.\n"
        "Для отмены отправьте /cancel"
    )
    
    await call.message.edit_text(text)
    await call.answer()


@router.message(PromoCodeStates.waiting_for_code, F.text)
async def process_promo_code(message: Message, state: FSMContext):
    """Process entered promo code."""
    code = message.text.strip().upper()
    
    async with DBSession() as session:
        from database.repositories.promo_code import PromoCodeRepository
        from database.models.promo_code import PromoCodeType
        
        promo_repo = PromoCodeRepository(session)
        master_repo = MasterRepository(session)
        
        master = await master_repo.get_by_telegram_id(message.from_user.id)
        if not master:
            await message.answer("❌ Ошибка: мастер не найден")
            await state.clear()
            return
        
        # Validate promo code
        promo_code = await promo_repo.get_promo_code(code)
        
        if not promo_code:
            await message.answer(
                f"❌ Промокод <code>{code}</code> не найден.\n"
                "Проверьте правильность ввода и попробуйте снова."
            )
            return
        
        # Check if valid
        validation = await promo_repo.validate_promo_code(code, master.id)
        
        if not validation['valid']:
            await message.answer(
                f"❌ Промокод <code>{code}</code> недействителен:\n"
                f"{validation['error']}"
            )
            return
        
        # Show promo code info and ask to choose plan
        if promo_code.type == PromoCodeType.PERCENT:
            discount_text = f"{promo_code.discount_percent}% скидка"
        elif promo_code.type == PromoCodeType.FIXED:
            discount_text = f"{promo_code.discount_amount}₽ скидка"
        else:
            discount_text = "Специальное предложение"
        
        text = (
            f"✅ <b>Промокод применён!</b>\n\n"
            f"🎫 Код: <code>{code}</code>\n"
            f"💰 {discount_text}\n\n"
            f"Выберите тариф для оплаты:"
        )
        
        # Save promo code to state
        await state.update_data(promo_code=code)
        await state.clear()
        
        await message.answer(text, reply_markup=get_plans_keyboard())


@router.message(Command("cancel"))
async def cancel_promo_input(message: Message, state: FSMContext):
    """Cancel promo code input."""
    current_state = await state.get_state()
    
    if current_state is None:
        await message.answer("Нечего отменять.")
        return
    
    await state.clear()
    await message.answer(
        "❌ Ввод промокода отменён.\n"
        "Используйте /subscription для возврата в меню."
    )

