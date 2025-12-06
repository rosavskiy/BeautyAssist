"""
Тесты для платежной системы
"""
import pytest
from database.models import Master, Transaction, TransactionStatus
from database.repositories.subscription import SubscriptionRepository
from services.payment import PaymentService


@pytest.mark.asyncio
async def test_payment_service_exists(db_session):
    """Тест: PaymentService существует и инициализируется"""
    payment_service = PaymentService(db_session)
    assert payment_service is not None


@pytest.mark.asyncio
async def test_create_transaction_record(db_session):
    """Тест создания записи о транзакции"""
    import secrets
    from datetime import datetime, timedelta
    from database.models.subscription import SubscriptionPlan, PaymentMethod
    
    master = Master(
        telegram_id=123456789,
        phone="+79001234567",
        name="Test Master",
        referral_code=secrets.token_urlsafe(8)
    )
    db_session.add(master)
    await db_session.commit()
    
    sub_repo = SubscriptionRepository(db_session)
    now = datetime.utcnow()
    subscription = await sub_repo.create_subscription(
        master_id=master.id,
        plan=SubscriptionPlan.MONTHLY,
        start_date=now,
        end_date=now + timedelta(days=30),
        amount=990,
        currency='RUB',
        payment_method=PaymentMethod.TELEGRAM_STARS
    )
    
    # Создаем транзакцию
    from database.models.transaction import TransactionType
    transaction = Transaction(
        master_id=master.id,
        subscription_id=subscription.id,
        type=TransactionType.SUBSCRIPTION,
        amount=990,
        currency='XTR',
        status=TransactionStatus.SUCCEEDED,
        payment_method='telegram_stars',
        provider_payment_id='test_charge_id'
    )
    db_session.add(transaction)
    await db_session.commit()
    
    assert transaction.id is not None
    assert transaction.amount == 990
    assert transaction.status == TransactionStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_subscription_plans_configuration():
    """Тест конфигурации тарифных планов"""
    from bot.subscription_plans import get_plan_config
    
    plans_list = ['trial', 'monthly', 'quarterly', 'yearly']
    
    for plan_id in plans_list:
        plan = get_plan_config(plan_id)
        assert plan is not None
    
    # Trial
    trial = get_plan_config('trial')
    assert trial.duration_days == 30
    assert trial.price_rub == 0
    assert trial.price_stars == 0
    
    # Monthly
    monthly = get_plan_config('monthly')
    assert monthly.duration_days == 30
    assert monthly.price_rub == 790
    assert monthly.price_stars == 790
    
    # Quarterly
    quarterly = get_plan_config('quarterly')
    assert quarterly.duration_days == 90
    assert quarterly.price_rub == 2490
    
    # Yearly
    yearly = get_plan_config('yearly')
    assert yearly.duration_days == 365
    assert yearly.price_rub == 8280


@pytest.mark.asyncio
async def test_trial_plan_is_free(db_session):
    """Тест: trial план бесплатный"""
    from bot.subscription_plans import get_plan_config
    trial = get_plan_config('trial')
    assert trial.price_rub == 0
    assert trial.price_stars == 0


@pytest.mark.asyncio
async def test_get_payment_stats(db_session):
    """Тест получения статистики платежей"""
    import secrets
    from datetime import datetime, timedelta
    from database.models.subscription import SubscriptionPlan, PaymentMethod
    
    master1 = Master(telegram_id=111, phone="+79001111111", name="Master 1", referral_code=secrets.token_urlsafe(8))
    master2 = Master(telegram_id=222, phone="+79002222222", name="Master 2", referral_code=secrets.token_urlsafe(8))
    db_session.add_all([master1, master2])
    await db_session.commit()
    
    sub_repo = SubscriptionRepository(db_session)
    now = datetime.utcnow()
    
    # Создаем несколько подписок
    for master in [master1, master2]:
        subscription = await sub_repo.create_subscription(
            master_id=master.id,
            plan=SubscriptionPlan.MONTHLY,
            start_date=now,
            end_date=now + timedelta(days=30),
            amount=990,
            currency='RUB',
            payment_method=PaymentMethod.TELEGRAM_STARS
        )
        
        # Создаем транзакцию
        from database.models.transaction import TransactionType
        transaction = Transaction(
            master_id=master.id,
            subscription_id=subscription.id,
            type=TransactionType.SUBSCRIPTION,
            amount=990,
            currency='XTR',
            status=TransactionStatus.SUCCEEDED,
            payment_method='telegram_stars'
        )
        db_session.add(transaction)
    
    await db_session.commit()
    
    # Получаем статистику
    from sqlalchemy import select, func
    result = await db_session.execute(
        select(
            func.count(Transaction.id).label('total_transactions'),
            func.sum(Transaction.amount).label('total_revenue')
        ).where(Transaction.status == "succeeded")
    )
    stats = result.first()
    
    assert stats.total_transactions == 2
    assert stats.total_revenue == 1980


