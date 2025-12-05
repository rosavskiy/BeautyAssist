"""
Тесты для системы подписок
"""
import pytest
import secrets
from datetime import datetime, timedelta
from database.models import Master, Subscription, SubscriptionStatus, Transaction, TransactionStatus
from database.repositories.subscription import SubscriptionRepository
from bot.subscription_plans import SUBSCRIPTION_PLANS


def generate_referral_code():
    """Генерирует уникальный реферальный код"""
    return secrets.token_urlsafe(8)


@pytest.mark.asyncio
async def test_create_subscription(db_session):
    """Тест создания подписки"""
    # Создаем мастера
    master = Master(telegram_id=123456789, phone="+79001234567", name="Test Master", referral_code="REF456789", referral_code=generate_referral_code()
    )
    db_session.add(master)
    await db_session.commit()
    
    # Создаем подписку
    repo = SubscriptionRepository(db_session)
    from bot.subscription_plans import get_plan_config; plan = get_plan_config('monthly')
    
    subscription = await repo.create_subscription(
        master_id=master.id,
        plan=plan['id'],
        amount=plan['price_rub'],
        duration_days=plan['duration_days']
    )
    
    assert subscription is not None
    assert subscription.master_id == master.id
    assert subscription.plan == 'monthly'
    assert subscription.amount == 990
    assert subscription.status == SubscriptionStatus.PENDING
    assert subscription.start_date is None
    assert subscription.end_date is None


@pytest.mark.asyncio
async def test_activate_subscription(db_session):
    """Тест активации подписки"""
    # Создаем мастера и подписку
    master = Master(telegram_id=123456789, phone="+79001234567", name="Test Master", referral_code="REF456789",
        is_premium=False
    )
    db_session.add(master)
    await db_session.commit()
    
    repo = SubscriptionRepository(db_session)
    subscription = await repo.create_subscription(
        master_id=master.id,
        plan='monthly',
        amount=990,
        duration_days=30
    )
    
    # Активируем подписку
    activated = await repo.activate_subscription(subscription.id)
    
    assert activated is not None
    assert activated.status == SubscriptionStatus.ACTIVE
    assert activated.start_date is not None
    assert activated.end_date is not None
    assert (activated.end_date - activated.start_date).days == 30
    
    # Проверяем, что мастер стал премиум
    await db_session.refresh(master)
    assert master.is_premium is True
    assert master.premium_until == activated.end_date


@pytest.mark.asyncio
async def test_activate_trial(db_session):
    """Тест активации пробного периода"""
    master = Master(telegram_id=123456789, phone="+79001234567", name="Test Master", referral_code="REF456789",
        is_premium=False
    )
    db_session.add(master)
    await db_session.commit()
    
    repo = SubscriptionRepository(db_session)
    subscription = await repo.activate_trial(master.id, trial_days=14)
    
    assert subscription is not None
    assert subscription.plan == 'trial'
    assert subscription.status == SubscriptionStatus.ACTIVE
    assert subscription.amount == 0
    assert (subscription.end_date - subscription.start_date).days == 14
    
    # Проверяем, что trial отмечен как использованный
    await db_session.refresh(master)
    assert master.trial_used is True
    assert master.is_premium is True


@pytest.mark.asyncio
async def test_trial_already_used(db_session):
    """Тест: нельзя использовать trial дважды"""
    master = Master(telegram_id=123456789, phone="+79001234567", name="Test Master", referral_code="REF456789",
        is_premium=False  # Уже использовал trial
    )
    db_session.add(master)
    await db_session.commit()
    
    repo = SubscriptionRepository(db_session)
    subscription = await repo.activate_trial(master.id, trial_days=14)
    
    assert subscription is None


@pytest.mark.asyncio
async def test_get_active_subscription(db_session):
    """Тест получения активной подписки"""
    master = Master(telegram_id=123456789, phone="+79001234567", name="Test Master", referral_code="REF456789"
    )
    db_session.add(master)
    await db_session.commit()
    
    repo = SubscriptionRepository(db_session)
    
    # Создаем и активируем подписку
    subscription = await repo.create_subscription(
        master_id=master.id,
        plan='monthly',
        amount=990,
        duration_days=30
    )
    await repo.activate_subscription(subscription.id)
    
    # Получаем активную подписку
    active = await repo.get_active_subscription(master.id)
    
    assert active is not None
    assert active.id == subscription.id
    assert active.status == SubscriptionStatus.ACTIVE


@pytest.mark.asyncio
async def test_get_expiring_subscriptions(db_session):
    """Тест получения истекающих подписок"""
    # Создаем мастера с подпиской, которая истекает через 2 дня
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
        start_date=now - timedelta(days=28),
        end_date=now + timedelta(days=2)
    )
    db_session.add(subscription)
    await db_session.commit()
    
    repo = SubscriptionRepository(db_session)
    
    # Получаем подписки, истекающие в течение 3 дней
    expiring = await repo.get_expiring_subscriptions(days=3)
    
    assert len(expiring) == 1
    assert expiring[0].id == subscription.id


@pytest.mark.asyncio
async def test_expire_subscription(db_session):
    """Тест истечения подписки"""
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
        start_date=now - timedelta(days=30),
        end_date=now - timedelta(days=1)  # Истекла вчера
    )
    db_session.add(subscription)
    await db_session.commit()
    
    repo = SubscriptionRepository(db_session)
    expired = await repo.expire_subscription(subscription.id)
    
    assert expired is not None
    assert expired.status == SubscriptionStatus.EXPIRED
    
    # Проверяем, что мастер больше не премиум
    await db_session.refresh(master)
    assert master.is_premium is False
    assert master.premium_until is None


@pytest.mark.asyncio
async def test_cancel_subscription(db_session):
    """Тест отмены подписки"""
    master = Master(telegram_id=123456789, phone="+79001234567", name="Test Master", referral_code="REF456789",
        is_premium=True
    )
    db_session.add(master)
    await db_session.commit()
    
    repo = SubscriptionRepository(db_session)
    subscription = await repo.create_subscription(
        master_id=master.id,
        plan='monthly',
        amount=990,
        duration_days=30
    )
    await repo.activate_subscription(subscription.id)
    
    # Отменяем подписку
    cancelled = await repo.cancel_subscription(subscription.id)
    
    assert cancelled is not None
    assert cancelled.status == SubscriptionStatus.CANCELLED
    
    # Проверяем, что мастер больше не премиум
    await db_session.refresh(master)
    assert master.is_premium is False


@pytest.mark.asyncio
async def test_subscription_plans_pricing(db_session):
    """Тест: проверка скидок в тарифах"""
    from bot.subscription_plans import PlanConfig, get_plan_config
    
    monthly = get_plan_config('monthly')
    quarterly = get_plan_config('quarterly')
    yearly = get_plan_config('yearly')
    
    # Monthly
    assert monthly.price_rub == 990
    assert monthly.price_stars == 990
    assert monthly.duration_days == 30
    
    # Quarterly: скидка 15%
    monthly_price_per_month = monthly.price_rub
    quarterly_price_per_month = quarterly.price_rub / 3
    quarterly_discount = (monthly_price_per_month - quarterly_price_per_month) / monthly_price_per_month * 100
    
    assert quarterly.price_rub == 2490
    assert abs(quarterly_discount - 15) < 1  # ~15% скидка
    
    # Yearly: скидка 30%
    yearly_price_per_month = yearly.price_rub / 12
    yearly_discount = (monthly_price_per_month - yearly_price_per_month) / monthly_price_per_month * 100
    
    assert yearly.price_rub == 8280
    assert abs(yearly_discount - 30) < 1  # ~30% скидка


@pytest.mark.asyncio
async def test_get_subscription_history(db_session):
    """Тест получения истории подписок"""
    master = Master(telegram_id=123456789, phone="+79001234567", name="Test Master", referral_code="REF456789"
    )
    db_session.add(master)
    await db_session.commit()
    
    repo = SubscriptionRepository(db_session)
    
    # Создаем несколько подписок
    sub1 = await repo.create_subscription(
        master_id=master.id,
        plan='trial',
        amount=0,
        duration_days=14
    )
    await repo.activate_subscription(sub1.id)
    await repo.expire_subscription(sub1.id)
    
    sub2 = await repo.create_subscription(
        master_id=master.id,
        plan='monthly',
        amount=990,
        duration_days=30
    )
    await repo.activate_subscription(sub2.id)
    
    # Получаем историю
    history = await repo.get_subscription_history(master.id, limit=10)
    
    assert len(history) == 2
    assert history[0].id == sub2.id  # Последняя подписка первой
    assert history[1].id == sub1.id


