"""Admin handlers for agent payouts management."""
import logging
from datetime import datetime
from collections import defaultdict

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from sqlalchemy import select, and_

from database.base import get_db
from database.repositories.referral import ReferralRepository
from database.repositories.master import MasterRepository
from database.models import Referral, Master

logger = logging.getLogger(__name__)

router = Router(name="admin_payouts")


async def get_admin_session():
    """Get database session for admin operations."""
    db_gen = get_db()
    session = await anext(db_gen)
    try:
        yield session
    finally:
        await db_gen.aclose()


@router.message(Command("admin_payouts"))
async def cmd_admin_payouts(message: Message):
    """Show pending agent payouts."""
    db_gen = get_db()
    session = await anext(db_gen)
    
    try:
        # Get all referrals with pending or failed payouts
        result = await session.execute(
            select(Referral, Master)
            .join(Master, Referral.referrer_id == Master.id)
            .where(
                and_(
                    Referral.status == 'activated',
                    Referral.payout_status.in_(['pending', 'failed'])
                )
            )
            .order_by(Referral.activated_at.desc())
        )
        
        pending_payouts = result.all()
        
        if not pending_payouts:
            await message.answer(
                "✅ <b>Все выплаты обработаны!</b>\n\n"
                "Нет невыплаченных комиссий агентам.",
                parse_mode="HTML"
            )
            return
        
        # Group by agent
        agent_payouts = defaultdict(lambda: {'stars': 0, 'count': 0, 'username': None, 'telegram_id': None})
        
        for referral, master in pending_payouts:
            agent_payouts[master.id]['stars'] += referral.commission_stars
            agent_payouts[master.id]['count'] += 1
            agent_payouts[master.id]['username'] = master.username or f"id{master.telegram_id}"
            agent_payouts[master.id]['telegram_id'] = master.telegram_id
            agent_payouts[master.id]['name'] = master.name
        
        # Format message
        text = "💰 <b>Невыплаченные комиссии агентам</b>\n\n"
        
        total_stars = 0
        total_agents = len(agent_payouts)
        
        for idx, (master_id, data) in enumerate(sorted(
            agent_payouts.items(), 
            key=lambda x: x[1]['stars'], 
            reverse=True
        ), 1):
            name = data['name'] or "Без имени"
            username = f"@{data['username']}" if data['username'] and not data['username'].startswith('id') else data['username']
            text += (
                f"{idx}. <b>{name}</b> ({username})\n"
                f"   💰 {data['stars']} ⭐ ({data['count']} реф.)\n\n"
            )
            total_stars += data['stars']
        
        text += f"━━━━━━━━━━━━━━━━━━━━\n"
        text += f"<b>Итого:</b> {total_stars} ⭐ ({total_agents} агентов)\n\n"
        text += (
            "📝 <b>Инструкция по выплате:</b>\n"
            "1. Откройте каждого агента в Telegram\n"
            "2. Отправьте Stars вручную\n"
            "3. После отправки используйте:\n"
            "   <code>/admin_mark_paid [telegram_id]</code>\n\n"
            "Пример: <code>/admin_mark_paid 123456789</code>"
        )
        
        await message.answer(text, parse_mode="HTML")
        
    finally:
        await db_gen.aclose()


@router.message(Command("admin_mark_paid"))
async def cmd_admin_mark_paid(message: Message):
    """Mark agent payouts as paid."""
    # Parse telegram_id from command
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer(
            "❌ <b>Неверный формат</b>\n\n"
            "Использование:\n"
            "<code>/admin_mark_paid [telegram_id]</code>\n\n"
            "Пример:\n"
            "<code>/admin_mark_paid 123456789</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        telegram_id = int(parts[1])
    except ValueError:
        await message.answer(
            "❌ Telegram ID должен быть числом",
            parse_mode="HTML"
        )
        return
    
    db_gen = get_db()
    session = await anext(db_gen)
    
    try:
        master_repo = MasterRepository(session)
        
        # Find master by telegram_id
        master = await master_repo.get_by_telegram_id(telegram_id)
        if not master:
            await message.answer(
                f"❌ Мастер с Telegram ID {telegram_id} не найден",
                parse_mode="HTML"
            )
            return
        
        # Update all pending payouts for this agent
        result = await session.execute(
            select(Referral)
            .where(
                and_(
                    Referral.referrer_id == master.id,
                    Referral.payout_status.in_(['pending', 'failed'])
                )
            )
        )
        
        referrals = result.scalars().all()
        
        if not referrals:
            await message.answer(
                f"✅ У агента <b>{master.name}</b> нет невыплаченных комиссий",
                parse_mode="HTML"
            )
            return
        
        # Mark as paid
        total_stars = 0
        for referral in referrals:
            referral.payout_status = 'sent'
            referral.payout_sent_at = datetime.utcnow()
            referral.payout_transaction_id = f"manual_{int(datetime.utcnow().timestamp())}"
            total_stars += referral.commission_stars
        
        await session.commit()
        
        await message.answer(
            f"✅ <b>Выплата отмечена!</b>\n\n"
            f"Агент: <b>{master.name}</b>\n"
            f"Telegram: @{master.username or telegram_id}\n"
            f"Сумма: <b>{total_stars} ⭐</b>\n"
            f"Рефералов: {len(referrals)}",
            parse_mode="HTML"
        )
        
    finally:
        await db_gen.aclose()


@router.message(Command("admin_payout_stats"))
async def cmd_admin_payout_stats(message: Message):
    """Show payout statistics."""
    db_gen = get_db()
    session = await anext(db_gen)
    
    try:
        from sqlalchemy import func
        
        # Total payouts
        result = await session.execute(
            select(
                func.count(Referral.id).label('total'),
                func.sum(Referral.commission_stars).label('total_stars')
            )
            .where(Referral.payout_status == 'sent')
        )
        
        stats = result.first()
        total_paid = stats.total or 0
        total_stars_paid = stats.total_stars or 0
        
        # Pending payouts
        result = await session.execute(
            select(
                func.count(Referral.id).label('pending'),
                func.sum(Referral.commission_stars).label('pending_stars')
            )
            .where(Referral.payout_status.in_(['pending', 'failed']))
        )
        
        pending_stats = result.first()
        total_pending = pending_stats.pending or 0
        total_pending_stars = pending_stats.pending_stars or 0
        
        text = (
            "📊 <b>Статистика выплат агентам</b>\n\n"
            f"✅ <b>Выплачено:</b>\n"
            f"   Транзакций: {total_paid}\n"
            f"   Сумма: {total_stars_paid} ⭐ (≈{total_stars_paid * 2}₽)\n\n"
            f"⏳ <b>Ожидают выплаты:</b>\n"
            f"   Транзакций: {total_pending}\n"
            f"   Сумма: {total_pending_stars} ⭐ (≈{total_pending_stars * 2}₽)\n\n"
            f"💎 <b>Всего выплат:</b>\n"
            f"   Транзакций: {total_paid + total_pending}\n"
            f"   Сумма: {total_stars_paid + total_pending_stars} ⭐\n\n"
            "Используйте /admin_payouts для обработки выплат"
        )
        
        await message.answer(text, parse_mode="HTML")
        
    finally:
        await db_gen.aclose()
