"""
Тесты для мониторинга подписок
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from database.models import Master, Subscription, SubscriptionStatus
from database.repositories.subscription import SubscriptionRepository
from services.subscription_monitor import SubscriptionMonitorService


@pytest.mark.asyncio
async def test_check_expiring_subscriptions_3_days(db_session):
    """Тест отправки напоминания за 3 дня"""
    # Создаем мастера с подпиской, истекающей через 3 дня
    master = Master(telegram_id=123456789, phone="+79001234567", name="Test Master", referral_code="REF456789",
        is_premium=True
    )
    db_session.add(master)
    await db_session.commit()
    
    now = datetime.utcnow()
    subscription = Subscription(
        master_id=master.id,
        plan='monthly',
        amount=990,
        status=SubscriptionStatus.ACTIVE,
        start_date=now - timedelta(days=27),
        end_date=now + timedelta(days=3, hours=12)  # Через 3.5 дня
    )
    db_session.add(subscription)
    await db_session.commit()
    
    # Мокаем бота
    mock_bot = AsyncMock()
    
    service = SubscriptionMonitorService(mock_bot)
    await service.check_expiring_subscriptions()
    
    # Проверяем, что сообщение было отправлено
    assert mock_bot.send_message.called
    call_args = mock_bot.send_message.call_args
    assert call_args.kwargs['chat_id'] == 123456789
    assert '3 дня' in call_args.kwargs['text'] or '3 дн' in call_args.kwargs['text']


@pytest.mark.asyncio
async def test_check_expiring_subscriptions_1_day(db_session):
    """Тест отправки напоминания за 1 день"""
    master = Master(telegram_id=123456789, phone="+79001234567", name="Test Master", referral_code="REF456789",
        is_premium=True
    )
    db_session.add(master)
    await db_session.commit()
    
    now = datetime.utcnow()
    subscription = Subscription(
        master_id=master.id,
        plan='monthly',
        amount=990,
        status=SubscriptionStatus.ACTIVE,
        start_date=now - timedelta(days=29),
        end_date=now + timedelta(days=1, hours=12)  # Через 1.5 дня
    )
    db_session.add(subscription)
    await db_session.commit()
    
    mock_bot = AsyncMock()
    
    service = SubscriptionMonitorService(mock_bot)
    await service.check_expiring_subscriptions()
    
    assert mock_bot.send_message.called
    call_args = mock_bot.send_message.call_args
    assert call_args.kwargs['chat_id'] == 123456789
    assert '1 день' in call_args.kwargs['text'] or 'завтра' in call_args.kwargs['text'].lower()


@pytest.mark.asyncio
async def test_auto_expire_subscription(db_session):
    """Тест автоматического истечения подписки"""
    master = Master(telegram_id=123456789, phone="+79001234567", name="Test Master", referral_code="REF456789",
        is_premium=True
    )
    db_session.add(master)
    await db_session.commit()
    
    now = datetime.utcnow()
    subscription = Subscription(
        master_id=master.id,
        plan='monthly',
        amount=990,
        status=SubscriptionStatus.ACTIVE,
        start_date=now - timedelta(days=35),
        end_date=now - timedelta(days=5)  # Истекла 5 дней назад
    )
    db_session.add(subscription)
    await db_session.commit()
    
    mock_bot = AsyncMock()
    
    service = SubscriptionMonitorService(mock_bot)
    await service.check_expiring_subscriptions()
    
    # Проверяем, что подписка истекла
    await db_session.refresh(subscription)
    assert subscription.status == SubscriptionStatus.EXPIRED
    
    # Проверяем, что мастер больше не премиум
    await db_session.refresh(master)
    assert master.is_premium is False
    assert master.premium_until is None
    
    # Проверяем, что уведомление отправлено
    assert mock_bot.send_message.called


@pytest.mark.asyncio
async def test_no_reminder_for_fresh_subscription(db_session):
    """Тест: нет напоминания для свежей подписки"""
    master = Master(telegram_id=123456789, phone="+79001234567", name="Test Master", referral_code="REF456789",
        is_premium=True
    )
    db_session.add(master)
    await db_session.commit()
    
    now = datetime.utcnow()
    subscription = Subscription(
        master_id=master.id,
        plan='monthly',
        amount=990,
        status=SubscriptionStatus.ACTIVE,
        start_date=now,
        end_date=now + timedelta(days=25)  # Еще 25 дней
    )
    db_session.add(subscription)
    await db_session.commit()
    
    mock_bot = AsyncMock()
    
    service = SubscriptionMonitorService(mock_bot)
    await service.check_expiring_subscriptions()
    
    # Проверяем, что уведомления не было
    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_multiple_subscriptions_different_stages(db_session):
    """Тест: обработка нескольких подписок на разных стадиях"""
    now = datetime.utcnow()
    
    # Мастер 1: подписка истекает через 3 дня
    master1 = Master(telegram_id=111, phone="+79001111111", name="Master 1", referral_code="REF111", is_premium=True)
    sub1 = Subscription(
        master_id=None,
        plan='monthly',
        amount=990,
        status=SubscriptionStatus.ACTIVE,
        start_date=now - timedelta(days=27),
        end_date=now + timedelta(days=3)
    )
    
    # Мастер 2: подписка истекает через 1 день
    master2 = Master(telegram_id=222, phone="+79002222222", name="Master 2", referral_code="REF222", is_premium=True)
    sub2 = Subscription(
        master_id=None,
        plan='monthly',
        amount=990,
        status=SubscriptionStatus.ACTIVE,
        start_date=now - timedelta(days=29),
        end_date=now + timedelta(days=1)
    )
    
    # Мастер 3: подписка истекла
    master3 = Master(telegram_id=333, phone="+79003333333", name="Master 3", referral_code="REF333", is_premium=True)
    sub3 = Subscription(
        master_id=None,
        plan='monthly',
        amount=990,
        status=SubscriptionStatus.ACTIVE,
        start_date=now - timedelta(days=35),
        end_date=now - timedelta(days=2)
    )
    
    db_session.add_all([master1, master2, master3])
    await db_session.commit()
    
    sub1.master_id = master1.id
    sub2.master_id = master2.id
    sub3.master_id = master3.id
    db_session.add_all([sub1, sub2, sub3])
    await db_session.commit()
    
    mock_bot = AsyncMock()
    
    service = SubscriptionMonitorService(mock_bot)
    await service.check_expiring_subscriptions()
    
    # Должно быть 3 вызова send_message (3 дня, 1 день, истекла)
    assert mock_bot.send_message.call_count == 3


@pytest.mark.asyncio
async def test_subscription_reminder_sent_flag(db_session):
    """Тест: напоминание не отправляется дважды"""
    master = Master(telegram_id=123456789, phone="+79001234567", name="Test Master", referral_code="REF456789",
        is_premium=True
    )
    db_session.add(master)
    await db_session.commit()
    
    now = datetime.utcnow()
    subscription = Subscription(
        master_id=master.id,
        plan='monthly',
        amount=990,
        status=SubscriptionStatus.ACTIVE,
        start_date=now - timedelta(days=27),
        end_date=now + timedelta(days=3)
    )
    db_session.add(subscription)
    await db_session.commit()
    
    mock_bot = AsyncMock()
    
    service = SubscriptionMonitorService(mock_bot)
    
    # Первый запуск - должно отправиться
    await service.check_expiring_subscriptions()
    assert mock_bot.send_message.call_count == 1
    
    # Помечаем, что напоминание отправлено
    await db_session.refresh(subscription)
    subscription.reminder_3d_sent = True
    await db_session.commit()
    
    # Второй запуск - не должно отправиться снова
    mock_bot.reset_mock()
    await service.check_expiring_subscriptions()
    assert mock_bot.send_message.call_count == 0


@pytest.mark.asyncio
async def test_error_handling_in_monitor(db_session):
    """Тест: обработка ошибок не прерывает работу"""
    master1 = Master(telegram_id=111, phone="+79001111111", name="Master 1", referral_code="REF111", is_premium=True)
    master2 = Master(telegram_id=222, phone="+79002222222", name="Master 2", referral_code="REF222", is_premium=True)
    db_session.add_all([master1, master2])
    await db_session.commit()
    
    now = datetime.utcnow()
    sub1 = Subscription(
        master_id=master1.id,
        plan='monthly',
        amount=990,
        status=SubscriptionStatus.ACTIVE,
        start_date=now - timedelta(days=27),
        end_date=now + timedelta(days=3)
    )
    sub2 = Subscription(
        master_id=master2.id,
        plan='monthly',
        amount=990,
        status=SubscriptionStatus.ACTIVE,
        start_date=now - timedelta(days=29),
        end_date=now + timedelta(days=1)
    )
    db_session.add_all([sub1, sub2])
    await db_session.commit()
    
    mock_bot = AsyncMock()
    # Первое сообщение вызывает ошибку, второе должно отправиться
    mock_bot.send_message.side_effect = [Exception("Network error"), None]
    
    service = SubscriptionMonitorService(mock_bot)
    
    # Не должно упасть
    await service.check_expiring_subscriptions()
    
    # Должно быть 2 попытки отправки
    assert mock_bot.send_message.call_count == 2

