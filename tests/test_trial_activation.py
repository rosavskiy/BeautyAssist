"""Test auto-activation of trial subscription on first /start."""
import pytest
from datetime import datetime, timedelta, timezone

from database.repositories.master import MasterRepository
from database.repositories.subscription import SubscriptionRepository
from database.models.subscription import SubscriptionPlan, SubscriptionStatus


@pytest.mark.asyncio
async def test_new_master_gets_trial_auto_activated(db_session):
    """Test that new master automatically gets trial subscription."""
    # Create a new master (simulating /start from new user)
    master_repo = MasterRepository(db_session)
    master = await master_repo.create(
        telegram_id=999999,
        name="New Test Master"
    )
    await db_session.commit()
    
    # Check that trial is available
    sub_repo = SubscriptionRepository(db_session)
    is_available = await sub_repo.is_trial_available(master.id)
    assert is_available is True
    
    # Simulate auto-activation (what happens in onboarding.py)
    from services.payment import PaymentService
    from unittest.mock import AsyncMock, MagicMock
    
    # Mock bot
    mock_bot = MagicMock()
    payment_service = PaymentService(mock_bot)
    
    success = await payment_service.activate_trial(
        master_id=master.id,
        telegram_id=999999,
        session=db_session,
    )
    
    assert success is True
    
    # Check subscription was created
    subscription = await sub_repo.get_active_subscription(master.id)
    assert subscription is not None
    assert subscription.plan == SubscriptionPlan.TRIAL.value
    assert subscription.status == SubscriptionStatus.ACTIVE.value
    
    # Check trial is no longer available
    is_available_after = await sub_repo.is_trial_available(master.id)
    assert is_available_after is False
    
    # Check subscription duration is 14 days
    duration = subscription.end_date - subscription.start_date
    assert duration.days == 14


@pytest.mark.asyncio
async def test_check_access_with_active_trial(db_session):
    """Test that active trial grants access."""
    master_repo = MasterRepository(db_session)
    master = await master_repo.create(
        telegram_id=888888,
        name="Trial Master"
    )
    
    sub_repo = SubscriptionRepository(db_session)
    now = datetime.now(timezone.utc)
    
    # Create active trial
    trial = await sub_repo.create_subscription(
        master_id=master.id,
        plan=SubscriptionPlan.TRIAL,
        start_date=now,
        end_date=now + timedelta(days=14),
        amount=0,
        currency="RUB"
    )
    await sub_repo.activate_subscription(trial.id)
    await db_session.commit()
    
    # Check access
    has_access = await sub_repo.check_access(master.id)
    assert has_access is True


@pytest.mark.asyncio
async def test_expired_trial_denies_access(db_session):
    """Test that expired trial does not grant access."""
    master_repo = MasterRepository(db_session)
    master = await master_repo.create(
        telegram_id=777777,
        name="Expired Trial Master"
    )
    
    sub_repo = SubscriptionRepository(db_session)
    now = datetime.now(timezone.utc)
    
    # Create expired trial
    trial = await sub_repo.create_subscription(
        master_id=master.id,
        plan=SubscriptionPlan.TRIAL,
        start_date=now - timedelta(days=20),
        end_date=now - timedelta(days=6),  # Expired 6 days ago
        amount=0,
        currency="RUB"
    )
    await sub_repo.activate_subscription(trial.id)
    await db_session.commit()
    
    # Subscription should be expired
    assert trial.is_active is False
    
    # Check access should be denied
    has_access = await sub_repo.check_access(master.id)
    assert has_access is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
