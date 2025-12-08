"""Export clients functionality."""
import logging
import csv
import io
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile
from aiogram.fsm.context import FSMContext

from database.base import async_session_maker
from database.repositories.master import MasterRepository
from database.repositories.client import ClientRepository
from database.repositories.subscription import SubscriptionRepository

logger = logging.getLogger(__name__)

router = Router(name="export")


@router.message(Command("export_clients"))
async def cmd_export_clients(message: Message, state: FSMContext):
    """
    Export clients database to CSV file.
    
    Available only for users with active paid subscription.
    """
    async with async_session_maker() as session:
        master_repo = MasterRepository(session)
        master = await master_repo.get_by_telegram_id(message.from_user.id)
        
        if not master:
            return await message.answer(
                "❌ Профиль не найден. Отправьте /start для регистрации."
            )
        
        # Check if user has active PAID subscription
        sub_repo = SubscriptionRepository(session)
        subscription = await sub_repo.get_active_subscription(master.id)
        
        if not subscription:
            return await message.answer(
                "❌ <b>Функция доступна только с активной подпиской</b>\n\n"
                "Экспорт базы клиентов доступен на всех платных тарифах.\n\n"
                "📱 Используйте /subscription для оформления подписки.",
                parse_mode="HTML"
            )
        
        # Check if it's trial subscription
        if subscription.plan_type == "trial":
            return await message.answer(
                "❌ <b>Функция недоступна на пробном периоде</b>\n\n"
                "Экспорт базы клиентов доступен только на платных тарифах:\n"
                "• Monthly (790₽/мес)\n"
                "• Quarterly (672₽/мес)\n"
                "• Yearly (553₽/мес)\n\n"
                "📱 Используйте /subscription для оформления платной подписки.",
                parse_mode="HTML"
            )
        
        # Get all clients
        client_repo = ClientRepository(session)
        clients = await client_repo.get_all_by_master(master.id, limit=10000)
        
        if not clients:
            return await message.answer(
                "📋 У вас пока нет клиентов в базе.\n\n"
                "Клиенты будут добавляться автоматически при записи через бота."
            )
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        
        # Write header
        writer.writerow([
            'ID',
            'Имя',
            'Телефон',
            'Telegram Username',
            'Email',
            'Заметки',
            'Всего визитов',
            'Общая сумма (₽)',
            'Последний визит',
            'Дата регистрации'
        ])
        
        # Write client data
        for client in clients:
            writer.writerow([
                client.id,
                client.name,
                client.phone or '',
                f"@{client.telegram_username}" if client.telegram_username else '',
                client.email or '',
                client.notes or '',
                client.total_visits or 0,
                client.total_spent or 0,
                client.last_visit.strftime('%d.%m.%Y %H:%M') if client.last_visit else '',
                client.created_at.strftime('%d.%m.%Y %H:%M') if client.created_at else ''
            ])
        
        # Convert to bytes
        csv_bytes = output.getvalue().encode('utf-8-sig')  # utf-8-sig for Excel compatibility
        output.close()
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"clients_export_{timestamp}.csv"
        
        # Create file object
        file = BufferedInputFile(csv_bytes, filename=filename)
        
        # Send file
        await message.answer_document(
            document=file,
            caption=(
                f"✅ <b>База клиентов экспортирована</b>\n\n"
                f"📊 Всего клиентов: {len(clients)}\n"
                f"📅 Дата экспорта: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                f"Файл можно открыть в Excel или Google Sheets."
            ),
            parse_mode="HTML"
        )
        
        logger.info(f"Exported {len(clients)} clients for master {master.id}")
