"""Referral program handlers."""
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from database.base import async_session_maker
from services.referral import ReferralService

logger = logging.getLogger(__name__)

router = Router(name="referral")


@router.message(Command("referral"))
async def cmd_referral(message: Message):
    """Show referral program information and statistics."""
    async with async_session_maker() as session:
        referral_service = ReferralService(session)
        
        # Get master ID from message
        master_id = message.from_user.id
        
        # Get statistics
        stats = await referral_service.get_statistics(master_id)
        
        # Generate referral link
        referral_link = ReferralService.generate_referral_link(master_id)
        
        # Compose message
        text = (
            "🎁 <b>Реферальная программа</b>\n\n"
            "Приглашай других мастеров и получай <b>+7 дней</b> подписки за каждого!\n\n"
            "📊 <b>Твоя статистика:</b>\n"
            f"Всего рефералов: <b>{stats['total']}</b>\n"
            f"├─ Активные: <b>{stats['activated']}</b> ✅\n"
            f"├─ Ожидают активации: <b>{stats['pending']}</b> ⏳\n"
            f"└─ Истёкшие: <b>{stats['expired']}</b> ❌\n\n"
            f"🎉 <b>Получено дней:</b> {stats['total_reward_days']}\n\n"
            "🔗 <b>Твоя реферальная ссылка:</b>\n"
            f"<code>{referral_link}</code>\n\n"
            "<i>Нажми на кнопку ниже, чтобы поделиться ссылкой!</i>"
        )
        
        # Add share button
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 Поделиться ссылкой",
                    switch_inline_query=(
                        f"Привет! Попробуй BeautyAssist - бота для мастеров бьюти-сферы. "
                        f"Регистрируйся по моей ссылке и получи 14 дней бесплатно! {referral_link}"
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Обновить статистику",
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
        
        master_id = callback_query.from_user.id
        
        # Get updated statistics
        stats = await referral_service.get_statistics(master_id)
        
        # Generate referral link
        referral_link = ReferralService.generate_referral_link(master_id)
        
        # Update message
        text = (
            "🎁 <b>Реферальная программа</b>\n\n"
            "Приглашай других мастеров и получай <b>+7 дней</b> подписки за каждого!\n\n"
            "📊 <b>Твоя статистика:</b>\n"
            f"Всего рефералов: <b>{stats['total']}</b>\n"
            f"├─ Активные: <b>{stats['activated']}</b> ✅\n"
            f"├─ Ожидают активации: <b>{stats['pending']}</b> ⏳\n"
            f"└─ Истёкшие: <b>{stats['expired']}</b> ❌\n\n"
            f"🎉 <b>Получено дней:</b> {stats['total_reward_days']}\n\n"
            "🔗 <b>Твоя реферальная ссылка:</b>\n"
            f"<code>{referral_link}</code>\n\n"
            "<i>Нажми на кнопку ниже, чтобы поделиться ссылкой!</i>"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 Поделиться ссылкой",
                    switch_inline_query=(
                        f"Привет! Попробуй BeautyAssist - бота для мастеров бьюти-сферы. "
                        f"Регистрируйся по моей ссылке и получи 14 дней бесплатно! {referral_link}"
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Обновить статистику",
                    callback_data="referral:refresh"
                )
            ]
        ])
        
        await callback_query.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback_query.answer("✅ Статистика обновлена")


def register_handlers(dp):
    """Register referral handlers."""
    dp.include_router(router)
