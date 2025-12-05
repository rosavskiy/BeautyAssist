"""Tests for admin metrics and analytics."""
import pytest
from datetime import datetime, timedelta, timezone

from database.repositories.admin import AdminRepository
from database.repositories.subscription import SubscriptionRepository
from database.repositories.master import MasterRepository
from database.models.subscription import SubscriptionPlan, SubscriptionStatus
from database.models.transaction import Transaction, TransactionStatus, TransactionType


@pytest.mark.asyncio
async def test_get_subscription_metrics_empty(db_session):
    """Test subscription metrics with no data."""
    admin_repo = AdminRepository(db_session)
    
    metrics = await admin_repo.get_subscription_metrics()
    
    assert metrics['mrr'] == 0
    assert metrics['total_active_subscriptions'] == 0
    assert metrics['conversion_rate'] == 0
    assert metrics['churn_rate'] == 0
    assert metrics['average_ltv'] == 0


@pytest.mark.asyncio
async def test_mrr_calculation(db_session):
    """Test MRR calculation for different subscription plans."""
    # Create master
    master_repo = MasterRepository(db_session)
    master = await master_repo.create(
        telegram_id=123456,
        name="test_master"
    )
    
    # Create subscriptions
    sub_repo = SubscriptionRepository(db_session)
    
    now = datetime.now(timezone.utc)
    
    # Monthly: 990₽
    await sub_repo.create_subscription(
        master_id=master.id,
        plan=SubscriptionPlan.MONTHLY,
        start_date=now,
        end_date=now + timedelta(days=30),
        amount=990,
        currency="RUB"
    )
    await sub_repo.activate_subscription(master.id)
    
    # Quarterly: 2490₽ (830₽/month)
    master2 = await master_repo.create(
        telegram_id=123457,
        name="test_master2"
    )
    await sub_repo.create_subscription(
        master_id=master2.id,
        plan=SubscriptionPlan.QUARTERLY,
        start_date=now,
        end_date=now + timedelta(days=90),
        amount=2490,
        currency="RUB"
    )
    await sub_repo.activate_subscription(master2.id)
    
    # Yearly: 8280₽ (690₽/month)
    master3 = await master_repo.create(
        telegram_id=123458,
        name="test_master3"
    )
    await sub_repo.create_subscription(
        master_id=master3.id,
        plan=SubscriptionPlan.YEARLY,
        start_date=now,
        end_date=now + timedelta(days=365),
        amount=8280,
        currency="RUB"
    )
    await sub_repo.activate_subscription(master3.id)
    
    await db_session.commit()
    
    # Calculate MRR
    admin_repo = AdminRepository(db_session)
    metrics = await admin_repo.get_subscription_metrics()
    
    # MRR = 990 + 2490/3 + 8280/12 = 990 + 830 + 690 = 2510
    assert metrics['mrr'] == 2510.0
    assert metrics['total_active_subscriptions'] == 3


@pytest.mark.asyncio
async def test_conversion_rate(db_session):
    """Test trial to paid conversion rate."""
    master_repo = MasterRepository(db_session)
    sub_repo = SubscriptionRepository(db_session)
    
    now = datetime.now(timezone.utc)
    
    # Create 5 trial users
    for i in range(5):
        master = await master_repo.create(
            telegram_id=100 + i,
            name=f"trial_user_{i}"
        )
        
        # Trial subscription
        trial_sub = await sub_repo.create_subscription(
            master_id=master.id,
            plan=SubscriptionPlan.TRIAL,
            start_date=now - timedelta(days=14),
            end_date=now,
            amount=0,
            currency="RUB"
        )
        await sub_repo.activate_subscription(trial_sub.id)
    
    # 2 of them converted to paid
    for i in range(2):
        master_id = i + 1  # First 2 masters
        paid_sub = await sub_repo.create_subscription(
            master_id=master_id,
            plan=SubscriptionPlan.MONTHLY,
            start_date=now,
            end_date=now + timedelta(days=30),
            amount=990,
            currency="RUB"
        )
        await sub_repo.activate_subscription(paid_sub.id)
    
    await db_session.commit()
    
    admin_repo = AdminRepository(db_session)
    metrics = await admin_repo.get_subscription_metrics()
    
    # Conversion = 2/5 = 40%
    assert metrics['total_trial_users'] == 5
    assert metrics['trial_conversions'] == 2
    assert metrics['conversion_rate'] == 40.0


@pytest.mark.asyncio
async def test_average_ltv(db_session):
    """Test average LTV calculation."""
    master_repo = MasterRepository(db_session)
    sub_repo = SubscriptionRepository(db_session)
    
    now = datetime.now(timezone.utc)
    
    # Create 3 paying customers
    for i in range(3):
        master = await master_repo.create(
            telegram_id=200 + i,
            name=f"paying_user_{i}"
        )
        
        # Monthly subscription
        sub = await sub_repo.create_subscription(
            master_id=master.id,
            plan=SubscriptionPlan.MONTHLY,
            start_date=now,
            end_date=now + timedelta(days=30),
            amount=990,
            currency="RUB"
        )
        await sub_repo.activate_subscription(master.id)
        
        # Create transaction
        transaction = Transaction(
            master_id=master.id,
            subscription_id=sub.id,
            amount=990,
            currency="RUB",
            type=TransactionType.SUBSCRIPTION.value,
            status=TransactionStatus.SUCCEEDED.value,
            payment_method="telegram_stars"
        )
        db_session.add(transaction)
    
    await db_session.commit()
    
    admin_repo = AdminRepository(db_session)
    metrics = await admin_repo.get_subscription_metrics()
    
    # LTV = 2970 / 3 = 990
    assert metrics['average_ltv'] == 990.0


@pytest.mark.asyncio
async def test_revenue_by_plan(db_session):
    """Test revenue breakdown by plan."""
    master_repo = MasterRepository(db_session)
    sub_repo = SubscriptionRepository(db_session)
    
    now = datetime.now(timezone.utc)
    
    # Create different plan subscriptions
    plans_data = [
        (SubscriptionPlan.MONTHLY, 990),
        (SubscriptionPlan.MONTHLY, 990),
        (SubscriptionPlan.QUARTERLY, 2490),
        (SubscriptionPlan.YEARLY, 8280),
    ]
    
    for idx, (plan, amount) in enumerate(plans_data):
        master = await master_repo.create(
            telegram_id=300 + idx,
            name=f"user_{idx}"
        )
        
        await sub_repo.create_subscription(
            master_id=master.id,
            plan=plan,
            start_date=now,
            end_date=now + timedelta(days=30),
            amount=amount,
            currency="RUB"
        )
        await sub_repo.activate_subscription(master.id)
    
    await db_session.commit()
    
    admin_repo = AdminRepository(db_session)
    metrics = await admin_repo.get_subscription_metrics()
    
    revenue = metrics['revenue_by_plan']
    assert revenue['monthly'] == 1980.0  # 990 * 2
    assert revenue['quarterly'] == 2490.0
    assert revenue['yearly'] == 8280.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
