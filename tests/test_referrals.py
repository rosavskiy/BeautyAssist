"""Tests for referral system."""
import pytest
from datetime import datetime, timedelta

from database.models import ReferralStatus
from database.repositories import ReferralRepository, MasterRepository
from services.referral import ReferralService


@pytest.mark.asyncio
async def test_generate_referral_link(db_session):
    """Test referral link generation."""
    master_id = 12345
    link = ReferralService.generate_referral_link(master_id)
    
    assert "t.me/" in link
    assert "start=ref_" in link
    
    # Decode and verify
    code = link.split("start=")[1]
    decoded_id = ReferralService.decode_referral_code(code)
    assert decoded_id == master_id


@pytest.mark.asyncio
async def test_create_referral(db_session):
    """Test creating a referral record."""
    master_repo = MasterRepository(db_session)
    referral_repo = ReferralRepository(db_session)
    
    # Create two masters
    referrer = await master_repo.create(
        telegram_id=111111,
        name="Referrer",
        telegram_username="referrer"
    )
    referred = await master_repo.create(
        telegram_id=222222,
        name="Referred",
        telegram_username="referred"
    )
    await db_session.commit()
    
    # Create referral
    referral = await referral_repo.create(
        referrer_id=referrer.id,
        referred_id=referred.id,
        reward_days=7
    )
    
    assert referral.referrer_id == referrer.id
    assert referral.referred_id == referred.id
    assert referral.status == ReferralStatus.PENDING.value
    assert referral.reward_given is False
    assert referral.reward_days == 7


@pytest.mark.asyncio
async def test_activate_referral(db_session):
    """Test activating a referral."""
    master_repo = MasterRepository(db_session)
    referral_repo = ReferralRepository(db_session)
    
    # Create masters
    referrer = await master_repo.create(
        telegram_id=333333,
        name="Referrer",
        telegram_username="referrer2"
    )
    referred = await master_repo.create(
        telegram_id=444444,
        name="Referred",
        telegram_username="referred2"
    )
    await db_session.commit()
    
    # Create referral
    referral = await referral_repo.create(
        referrer_id=referrer.id,
        referred_id=referred.id
    )
    
    # Activate
    activated = await referral_repo.activate(referral.id)
    
    assert activated.status == ReferralStatus.ACTIVATED.value
    assert activated.reward_given is True
    assert activated.activated_at is not None


@pytest.mark.asyncio
async def test_get_statistics(db_session):
    """Test getting referral statistics."""
    master_repo = MasterRepository(db_session)
    referral_repo = ReferralRepository(db_session)
    
    # Create referrer
    referrer = await master_repo.create(
        telegram_id=555555,
        name="Referrer",
        telegram_username="referrer3"
    )
    await db_session.commit()
    
    # Create 3 referred masters with different statuses
    for i in range(3):
        referred = await master_repo.create(
            telegram_id=600000 + i,
            name=f"Referred {i}",
            telegram_username=f"referred{i}"
        )
        await db_session.commit()
        
        referral = await referral_repo.create(
            referrer_id=referrer.id,
            referred_id=referred.id,
            reward_days=7
        )
        
        # Activate first one
        if i == 0:
            await referral_repo.activate(referral.id)
    
    # Get statistics
    stats = await referral_repo.get_statistics(referrer.id)
    
    assert stats['pending'] == 2
    assert stats['activated'] == 1
    assert stats['expired'] == 0
    assert stats['total_reward_days'] == 7


@pytest.mark.asyncio
async def test_expire_old_referrals(db_session):
    """Test expiring old pending referrals."""
    master_repo = MasterRepository(db_session)
    referral_repo = ReferralRepository(db_session)
    
    # Create masters
    referrer = await master_repo.create(
        telegram_id=777777,
        name="Referrer",
        telegram_username="referrer4"
    )
    referred = await master_repo.create(
        telegram_id=888888,
        name="Referred",
        telegram_username="referred4"
    )
    await db_session.commit()
    
    # Create referral
    referral = await referral_repo.create(
        referrer_id=referrer.id,
        referred_id=referred.id
    )
    
    # Manually set created_at to 31 days ago
    referral.created_at = datetime.utcnow() - timedelta(days=31)
    await db_session.commit()
    
    # Expire old referrals
    count = await referral_repo.expire_old_referrals(days=30)
    
    assert count == 1
    
    # Verify status
    await db_session.refresh(referral)
    assert referral.status == ReferralStatus.EXPIRED.value


@pytest.mark.asyncio
async def test_duplicate_referral(db_session):
    """Test that duplicate referrals are detected."""
    master_repo = MasterRepository(db_session)
    referral_repo = ReferralRepository(db_session)
    
    # Create masters
    referrer = await master_repo.create(
        telegram_id=999999,
        name="Referrer",
        telegram_username="referrer5"
    )
    referred = await master_repo.create(
        telegram_id=101010,
        name="Referred",
        telegram_username="referred5"
    )
    await db_session.commit()
    
    # Create first referral
    await referral_repo.create(
        referrer_id=referrer.id,
        referred_id=referred.id
    )
    
    # Check for duplicate
    is_duplicate = await referral_repo.check_duplicate(
        referrer_id=referrer.id,
        referred_id=referred.id
    )
    
    assert is_duplicate is True


@pytest.mark.asyncio
async def test_referral_service_create(db_session):
    """Test ReferralService.create_referral method."""
    master_repo = MasterRepository(db_session)
    referral_service = ReferralService(db_session)
    
    # Create masters
    referrer = await master_repo.create(
        telegram_id=111000,
        name="Referrer",
        telegram_username="referrer6"
    )
    referred = await master_repo.create(
        telegram_id=222000,
        name="Referred",
        telegram_username="referred6"
    )
    await db_session.commit()
    
    # Create referral through service
    result = await referral_service.create_referral(
        referrer_id=referrer.id,
        referred_id=referred.id
    )
    
    assert result['success'] is True
    assert 'referral_id' in result


@pytest.mark.asyncio
async def test_self_referral_prevention(db_session):
    """Test that self-referral is prevented."""
    master_repo = MasterRepository(db_session)
    referral_service = ReferralService(db_session)
    
    # Create master
    master = await master_repo.create(
        telegram_id=333000,
        name="Master",
        telegram_username="master1"
    )
    await db_session.commit()
    
    # Try to create self-referral
    result = await referral_service.create_referral(
        referrer_id=master.id,
        referred_id=master.id
    )
    
    assert result['success'] is False
    assert 'yourself' in result['message'].lower()
