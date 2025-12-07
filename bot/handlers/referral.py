"""Referral program handlers."""
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

from database.base import async_session_maker
from services.referral import ReferralService
from services.agent_payout import AgentPayoutService
from bot.main import bot

logger = logging.getLogger(__name__)

router = Router(name="referral")


@router.message(Command("referral"))
async def cmd_referral(message: Message):
    """Show referral program information and statistics."""
    async with async_session_maker() as session:
        referral_service = ReferralService(session)
        payout_service = AgentPayoutService(session, bot)
        
        # Get master ID from message
        master_id = message.from_user.id
        
        # Get statistics
        stats = await referral_service.get_statistics(master_id)
        
        # Get earnings statistics
        earnings = await payout_service.get_agent_earnings(master_id)
        
        # Generate referral link
        referral_link = ReferralService.generate_referral_link(master_id)
        
        # Compose message with new agent network model
        total_referrals = stats['activated'] + stats['pending'] + stats['expired']
        total_stars = earnings.get('total_stars_earned', 0) if earnings.get('success') else 0
        
        text = (
            "🎁 <b>Партнёрская программа</b>\n\n"
            "Приглашай мастеров и получай <b>10% от их оплат в звёздах!</b>\n\n"
            "💼 <b>Твоя статистика:</b>\n"
            f"├─ Всего рефералов: <b>{total_referrals}</b>\n"
            f"├─ Активных (оплатили): <b>{stats['activated']}</b> ✅\n"
            f"├─ Ожидают оплаты: <b>{stats['pending']}</b> ⏳\n"
            f"└─ Истёкшие: <b>{stats['expired']}</b> ❌\n\n"
            f"💰 <b>Заработано звёзд:</b> {total_stars} ⭐\n\n"
            "💡 <i>Например: Мастер оплачивает 390⭐ → Вы получаете 39⭐</i>\n\n"
            "🔗 <b>Твоя реферальная ссылка:</b>\n"
            f"<code>{referral_link}</code>\n\n"
            "<i>Нажми на кнопку ниже, чтобы поделиться!</i>"
        )
        
        # Add buttons
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 Поделиться ссылкой",
                    switch_inline_query=(
                        f"Привет! Попробуй BeautyAssist - бота для мастеров бьюти-сферы. "
                        f"Регистрируйся по моей ссылке и получи 30 дней бесплатно! {referral_link}"
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    text="💰 История выплат",
                    callback_data="payouts:show"
                ),
                InlineKeyboardButton(
                    text="🔄 Обновить",
                    callback_data="referral:refresh"
                )
            ]
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "referral:refresh")
async def callback_refresh_stats(callback_query):
    """Refresh referral statistics."""
    async with async_session_maker() as session:
        referral_service = ReferralService(session)
        payout_service = AgentPayoutService(session, bot)
        
        master_id = callback_query.from_user.id
        
        # Get updated statistics
        stats = await referral_service.get_statistics(master_id)
        
        # Get earnings statistics
        earnings = await payout_service.get_agent_earnings(master_id)
        
        # Generate referral link
        referral_link = ReferralService.generate_referral_link(master_id)
        
        # Update message with new model
        total_referrals = stats['activated'] + stats['pending'] + stats['expired']
        total_stars = earnings.get('total_stars_earned', 0) if earnings.get('success') else 0
        
        text = (
            "🎁 <b>Партнёрская программа</b>\n\n"
            "Приглашай мастеров и получай <b>10% от их оплат в звёздах!</b>\n\n"
            "💼 <b>Твоя статистика:</b>\n"
            f"├─ Всего рефералов: <b>{total_referrals}</b>\n"
            f"├─ Активных (оплатили): <b>{stats['activated']}</b> ✅\n"
            f"├─ Ожидают оплаты: <b>{stats['pending']}</b> ⏳\n"
            f"└─ Истёкшие: <b>{stats['expired']}</b> ❌\n\n"
            f"💰 <b>Заработано звёзд:</b> {total_stars} ⭐\n\n"
            "💡 <i>Например: Мастер оплачивает 390⭐ → Вы получаете 39⭐</i>\n\n"
            "🔗 <b>Твоя реферальная ссылка:</b>\n"
            f"<code>{referral_link}</code>\n\n"
            "<i>Нажми на кнопку ниже, чтобы поделиться!</i>"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 Поделиться ссылкой",
                    switch_inline_query=(
                        f"Привет! Попробуй BeautyAssist - бота для мастеров бьюти-сферы. "
                        f"Регистрируйся по моей ссылке и получи 30 дней бесплатно! {referral_link}"
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    text="💰 История выплат",
                    callback_data="payouts:show"
                ),
                InlineKeyboardButton(
                    text="🔄 Обновить",
                    callback_data="referral:refresh"
                )
            ]
        ])
        
        try:
            await callback_query.message.edit_text(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            await callback_query.answer("✅ Статистика обновлена")
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                await callback_query.answer("📊 Статистика актуальна", show_alert=False)
            else:
                raise


@router.message(Command("payouts"))
async def cmd_payouts(message: Message):
    """Show agent's payout history."""
    async with async_session_maker() as session:
        payout_service = AgentPayoutService(session, bot)
        
        master_id = message.from_user.id
        
        # Get earnings data
        earnings = await payout_service.get_agent_earnings(master_id)
        
        if not earnings.get('success'):
            await message.answer(
                "❌ Не удалось загрузить историю выплат.\n"
                "Попробуйте позже.",
                parse_mode="HTML"
            )
            return
        
        total_stars = earnings['total_stars_earned']
        payouts_sent = earnings['payouts_sent']
        payouts_pending = earnings['payouts_pending']
        payout_history = earnings['payout_history']
        
        # Compose message
        text = "💰 <b>История выплат в звёздах</b>\n\n"
        
        if not payout_history:
            text += (
                "У вас пока нет выплат.\n\n"
                "💡 Приглашайте мастеров и получайте 10% от их оплат!\n"
                "Используйте /referral для получения реферальной ссылки."
            )
        else:
            # Group by month
            from datetime import datetime
            from collections import defaultdict
            
            monthly_data = defaultdict(list)
            for payout in payout_history[:10]:  # Last 10 payouts
                if payout['date']:
                    month_key = payout['date'].strftime("%B %Y")
                    monthly_data[month_key].append(payout)
            
            # Show payouts grouped by month
            for month, payouts in list(monthly_data.items())[:3]:  # Last 3 months
                text += f"📅 <b>{month}:</b>\n"
                month_total = sum(p['amount'] for p in payouts)
                for p in payouts:
                    date_str = p['date'].strftime("%d %b")
                    text += f"├─ {date_str}: +{p['amount']} ⭐\n"
                text += f"└─ Итого: {month_total} ⭐\n\n"
            
            text += f"💎 <b>Всего заработано:</b> {total_stars} ⭐\n"
            text += f"📊 <b>Выплат получено:</b> {payouts_sent}\n"
            
            if payouts_pending > 0:
                text += f"⏳ <b>Ожидают:</b> {payouts_pending}\n"
            
            text += "\nℹ️ <i>Звёзды можно использовать в Telegram или обменять на рубли</i>"
        
        # Add keyboard
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 Назад к статистике",
                    callback_data="referral:show"
                )
            ]
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "payouts:show")
async def callback_show_payouts(callback_query):
    """Show payouts via callback."""
    async with async_session_maker() as session:
        payout_service = AgentPayoutService(session, bot)
        
        master_id = callback_query.from_user.id
        
        # Get earnings data
        earnings = await payout_service.get_agent_earnings(master_id)
        
        if not earnings.get('success'):
            await callback_query.answer("❌ Не удалось загрузить данные", show_alert=True)
            return
        
        total_stars = earnings['total_stars_earned']
        payouts_sent = earnings['payouts_sent']
        payouts_pending = earnings['payouts_pending']
        payout_history = earnings['payout_history']
        
        # Compose message
        text = "💰 <b>История выплат в звёздах</b>\n\n"
        
        if not payout_history:
            text += (
                "У вас пока нет выплат.\n\n"
                "💡 Приглашайте мастеров и получайте 10% от их оплат!\n"
                "Используйте /referral для получения реферальной ссылки."
            )
        else:
            # Group by month
            from datetime import datetime
            from collections import defaultdict
            
            monthly_data = defaultdict(list)
            for payout in payout_history[:10]:
                if payout['date']:
                    month_key = payout['date'].strftime("%B %Y")
                    monthly_data[month_key].append(payout)
            
            # Show payouts
            for month, payouts in list(monthly_data.items())[:3]:
                text += f"📅 <b>{month}:</b>\n"
                month_total = sum(p['amount'] for p in payouts)
                for p in payouts:
                    date_str = p['date'].strftime("%d %b")
                    text += f"├─ {date_str}: +{p['amount']} ⭐\n"
                text += f"└─ Итого: {month_total} ⭐\n\n"
            
            text += f"💎 <b>Всего заработано:</b> {total_stars} ⭐\n"
            text += f"📊 <b>Выплат получено:</b> {payouts_sent}\n"
            
            if payouts_pending > 0:
                text += f"⏳ <b>Ожидают:</b> {payouts_pending}\n"
            
            text += "\nℹ️ <i>Звёзды можно использовать в Telegram или обменять на рубли</i>"
        
        # Add keyboard
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 Назад к статистике",
                    callback_data="referral:show"
                )
            ]
        ])
        
        try:
            await callback_query.message.edit_text(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            await callback_query.answer()
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                await callback_query.answer("📊 Данные актуальны")
            else:
                raise


@router.callback_query(F.data == "referral:show")
async def callback_show_referral(callback_query):
    """Show referral stats via callback."""
    async with async_session_maker() as session:
        referral_service = ReferralService(session)
        payout_service = AgentPayoutService(session, bot)
        
        master_id = callback_query.from_user.id
        
        # Get statistics
        stats = await referral_service.get_statistics(master_id)
        earnings = await payout_service.get_agent_earnings(master_id)
        
        # Generate referral link
        referral_link = ReferralService.generate_referral_link(master_id)
        
        total_referrals = stats['activated'] + stats['pending'] + stats['expired']
        total_stars = earnings.get('total_stars_earned', 0) if earnings.get('success') else 0
        
        text = (
            "🎁 <b>Партнёрская программа</b>\n\n"
            "Приглашай мастеров и получай <b>10% от их оплат в звёздах!</b>\n\n"
            "💼 <b>Твоя статистика:</b>\n"
            f"├─ Всего рефералов: <b>{total_referrals}</b>\n"
            f"├─ Активных (оплатили): <b>{stats['activated']}</b> ✅\n"
            f"├─ Ожидают оплаты: <b>{stats['pending']}</b> ⏳\n"
            f"└─ Истёкшие: <b>{stats['expired']}</b> ❌\n\n"
            f"💰 <b>Заработано звёзд:</b> {total_stars} ⭐\n\n"
            "💡 <i>Например: Мастер оплачивает 390⭐ → Вы получаете 39⭐</i>\n\n"
            "🔗 <b>Твоя реферальная ссылка:</b>\n"
            f"<code>{referral_link}</code>\n\n"
            "<i>Нажми на кнопку ниже, чтобы поделиться!</i>"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 Поделиться ссылкой",
                    switch_inline_query=(
                        f"Привет! Попробуй BeautyAssist - бота для мастеров бьюти-сферы. "
                        f"Регистрируйся по моей ссылке и получи 30 дней бесплатно! {referral_link}"
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    text="💰 История выплат",
                    callback_data="payouts:show"
                ),
                InlineKeyboardButton(
                    text="🔄 Обновить",
                    callback_data="referral:refresh"
                )
            ]
        ])
        
        try:
            await callback_query.message.edit_text(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            await callback_query.answer()
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                await callback_query.answer("📊 Данные актуальны")
            else:
                raise


def register_handlers(dp):
    """Register referral handlers."""
    dp.include_router(router)
