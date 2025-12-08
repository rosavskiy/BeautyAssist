"""Support system handlers."""
import logging
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.config import settings

logger = logging.getLogger(__name__)

router = Router(name="support")


class SupportStates(StatesGroup):
    """States for support system."""
    waiting_for_message = State()


@router.message(Command("support"))
async def cmd_support(message: Message, state: FSMContext):
    """
    Handle /support command.
    
    Allows users to send a message to support admin.
    """
    if not settings.support_admin_id:
        await message.answer(
            "❌ Система поддержки временно недоступна.\n"
            "Пожалуйста, попробуйте позже."
        )
        return
    
    await state.set_state(SupportStates.waiting_for_message)
    await message.answer(
        "💬 <b>Обращение в поддержку</b>\n\n"
        "Напишите ваш вопрос или проблему одним сообщением.\n"
        "Мы получим его и ответим вам как можно скорее.\n\n"
        "Для отмены отправьте /cancel",
        parse_mode="HTML"
    )


@router.message(SupportStates.waiting_for_message, Command("cancel"))
async def cancel_support(message: Message, state: FSMContext):
    """Cancel support request."""
    await state.clear()
    await message.answer(
        "❌ Обращение в поддержку отменено.\n"
        "Если понадобится помощь, отправьте /support"
    )


@router.message(SupportStates.waiting_for_message)
async def process_support_message(message: Message, state: FSMContext, bot: Bot):
    """
    Process user's support message and forward to admin.
    
    Sends the message to the support admin with user information.
    """
    if not settings.support_admin_id:
        await message.answer("❌ Система поддержки временно недоступна.")
        await state.clear()
        return
    
    user = message.from_user
    user_info = (
        f"👤 <b>Новое обращение в поддержку</b>\n\n"
        f"<b>От:</b> {user.full_name}\n"
        f"<b>Username:</b> @{user.username or 'нет'}\n"
        f"<b>ID:</b> <code>{user.id}</code>\n"
        f"<b>Дата:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"<b>Сообщение:</b>\n{message.text or message.caption or '[медиа без текста]'}"
    )
    
    try:
        # Forward message to support admin
        await bot.send_message(
            chat_id=settings.support_admin_id,
            text=user_info,
            parse_mode="HTML"
        )
        
        # If message contains media, forward it as well
        if message.photo or message.video or message.document:
            await message.forward(settings.support_admin_id)
        
        await message.answer(
            "✅ <b>Ваше обращение отправлено!</b>\n\n"
            "Мы получили ваше сообщение и ответим вам как можно скорее.\n"
            "Обычно это занимает несколько часов.",
            parse_mode="HTML"
        )
        
        logger.info(f"Support request from user {user.id} forwarded to admin {settings.support_admin_id}")
        
    except Exception as e:
        logger.error(f"Failed to forward support message: {e}")
        await message.answer(
            "❌ Произошла ошибка при отправке сообщения.\n"
            "Пожалуйста, попробуйте позже."
        )
    
    await state.clear()
