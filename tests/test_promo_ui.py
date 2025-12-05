"""Tests for promo code UI functionality."""
import pytest
from datetime import datetime, timezone

from database.repositories.promo_code import PromoCodeRepository
from database.repositories.master import MasterRepository
from database.models.promo_code import PromoCodeType


@pytest.mark.asyncio
async def test_promo_code_validation_success(db_session):
    """Test successful promo code validation."""
    # Create master
    master_repo = MasterRepository(db_session)
    master = await master_repo.create(
        telegram_id=999888,
        name="promo_test_user"
    )
    
    # Create promo code
    promo_repo = PromoCodeRepository(db_session)
    promo = await promo_repo.create_promo_code(
        code="TESTCODE",
        type=PromoCodeType.PERCENT,
        discount_percent=20,
        max_uses=100
    )
    
    await db_session.commit()
    
    # Validate
    is_valid, error, promo_result = await promo_repo.validate_promo_code("TESTCODE", master.id)
    
    assert is_valid is True
    assert error is None
    assert promo_result is not None


@pytest.mark.asyncio
async def test_promo_code_not_found(db_session):
    """Test promo code not found."""
    master_repo = MasterRepository(db_session)
    master = await master_repo.create(
        telegram_id=999889,
        name="promo_test_user2"
    )
    
    await db_session.commit()
    
    promo_repo = PromoCodeRepository(db_session)
    promo = await promo_repo.get_promo_code("NONEXISTENT")
    
    assert promo is None


@pytest.mark.asyncio
async def test_promo_code_case_insensitive(db_session):
    """Test promo code is case insensitive."""
    promo_repo = PromoCodeRepository(db_session)
    
    # Create promo code
    await promo_repo.create_promo_code(
        code="SUMMER2025",
        type=PromoCodeType.PERCENT,
        discount_percent=15
    )
    
    await db_session.commit()
    
    # Try different cases
    promo_upper = await promo_repo.get_promo_code("SUMMER2025")
    promo_lower = await promo_repo.get_promo_code("summer2025")
    promo_mixed = await promo_repo.get_promo_code("SuMmEr2025")
    
    assert promo_upper is not None
    assert promo_lower is not None
    assert promo_mixed is not None
    assert promo_upper.code == promo_lower.code == promo_mixed.code


@pytest.mark.asyncio
async def test_promo_code_max_uses_limit(db_session):
    """Test promo code max uses limit."""
    master_repo = MasterRepository(db_session)
    promo_repo = PromoCodeRepository(db_session)
    
    # Create promo code with max_uses=1
    await promo_repo.create_promo_code(
        code="LIMITEDCODE",
        type=PromoCodeType.PERCENT,
        discount_percent=10,
        max_uses=1
    )
    
    # Create master
    master = await master_repo.create(
        telegram_id=999890,
        name="promo_test_user3"
    )
    
    await db_session.commit()
    
    # First use - should be valid
    is_valid1, error1, promo = await promo_repo.validate_promo_code("LIMITEDCODE", master.id)
    assert is_valid1 is True
    
    # Apply promo code (need subscription_id and amount)
    is_valid, error, promo = await promo_repo.validate_promo_code("LIMITEDCODE", master.id)
    assert is_valid
    # Apply it
    await promo_repo.apply_promo_code(promo, master.id, subscription_id=None, original_amount=1000)
    await db_session.commit()
    
    # Create another master
    master2 = await master_repo.create(
        telegram_id=999891,
        name="promo_test_user4"
    )
    await db_session.commit()
    
    # Second use - should be invalid (max uses reached)
    is_valid2, error2, _ = await promo_repo.validate_promo_code("LIMITEDCODE", master2.id)
    assert is_valid2 is False
    assert error2 is not None


@pytest.mark.asyncio
async def test_promo_code_per_user_limit(db_session):
    """Test promo code max uses per user limit."""
    master_repo = MasterRepository(db_session)
    promo_repo = PromoCodeRepository(db_session)
    
    # Create promo code with max_uses_per_user=1
    await promo_repo.create_promo_code(
        code="ONCEPERUSER",
        type=PromoCodeType.FIXED,
        discount_amount=500,
        max_uses_per_user=1
    )
    
    # Create master
    master = await master_repo.create(
        telegram_id=999892,
        name="promo_test_user5"
    )
    
    await db_session.commit()
    
    # First use - should be valid
    is_valid1, error1, promo = await promo_repo.validate_promo_code("ONCEPERUSER", master.id)
    assert is_valid1 is True
    
    # Apply promo code
    await promo_repo.apply_promo_code(promo, master.id, subscription_id=None, original_amount=1000)
    await db_session.commit()
    
    # Try to use again - should be invalid
    is_valid2, error2, _ = await promo_repo.validate_promo_code("ONCEPERUSER", master.id)
    assert is_valid2 is False
    assert 'уже использовали' in error2.lower()


@pytest.mark.asyncio
async def test_promo_code_inactive_status(db_session):
    """Test inactive promo code validation."""
    master_repo = MasterRepository(db_session)
    promo_repo = PromoCodeRepository(db_session)
    
    # Create promo code and deactivate it
    promo = await promo_repo.create_promo_code(
        code="INACTIVECODE",
        type=PromoCodeType.PERCENT,
        discount_percent=25
    )
    await promo_repo.deactivate_promo_code("INACTIVECODE")
    
    # Create master
    master = await master_repo.create(
        telegram_id=999893,
        name="promo_test_user6"
    )
    
    await db_session.commit()
    
    # Should be invalid
    is_valid, error, _ = await promo_repo.validate_promo_code("INACTIVECODE", master.id)
    assert is_valid is False
    assert 'деактивирован' in error.lower()


@pytest.mark.asyncio
async def test_promo_code_stats(db_session):
    """Test promo code statistics."""
    master_repo = MasterRepository(db_session)
    promo_repo = PromoCodeRepository(db_session)
    
    # Create promo code
    await promo_repo.create_promo_code(
        code="STATSCODE",
        type=PromoCodeType.PERCENT,
        discount_percent=20
    )
    
    # Create 3 users and apply promo code
    promo = await promo_repo.get_promo_code("STATSCODE")
    for i in range(3):
        master = await master_repo.create(
            telegram_id=555000 + i,
            name=f"stats_user_{i}"
        )
        # subscription_id can be None for testing
        await promo_repo.apply_promo_code(promo, master.id, subscription_id=None, original_amount=990)
    
    await db_session.commit()
    
    # Get stats
    stats = await promo_repo.get_promo_code_stats("STATSCODE")
    
    assert stats['usage_count'] == 3
    # 20% discount on 990 = 198 per user, 198 * 3 = 594
    assert stats['total_discount_given'] == 594


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
