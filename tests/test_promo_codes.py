"""
Тесты для системы промокодов
"""
import pytest
from datetime import datetime, timedelta
from database.models import Master, Subscription, SubscriptionStatus, PromoCode, PromoCodeType, PromoCodeStatus, PromoCodeUsage
from database.repositories.promo_code import PromoCodeRepository
from database.repositories.subscription import SubscriptionRepository


@pytest.mark.asyncio
async def test_create_promo_code(db_session):
    """Тест создания промокода"""
    repo = PromoCodeRepository(db_session)
    
    promo = await repo.create_promo_code(
        code="TEST20",
        type=PromoCodeType.PERCENT,
        discount_percent=20,
        max_uses=100,
        max_uses_per_user=1
    )
    
    assert promo is not None
    assert promo.code == "TEST20"
    assert promo.type == PromoCodeType.PERCENT
    assert promo.discount_percent == 20
    assert promo.status == PromoCodeStatus.ACTIVE
    assert promo.max_uses == 100
    assert promo.max_uses_per_user == 1
    assert promo.current_uses == 0


@pytest.mark.asyncio
async def test_get_promo_code(db_session):
    """Тест получения промокода по коду"""
    repo = PromoCodeRepository(db_session)
    
    await repo.create_promo_code(
        code="SUMMER50",
        type=PromoCodeType.PERCENT,
        discount_percent=50
    )
    
    # Получаем по коду (регистронезависимый)
    promo = await repo.get_promo_code("summer50")
    
    assert promo is not None
    assert promo.code == "SUMMER50"
    assert promo.discount_percent == 50


@pytest.mark.asyncio
async def test_validate_promo_code_success(db_session):
    """Тест успешной валидации промокода"""
    master = Master(telegram_id=123456789, phone="+79001234567", name="Test Master", referral_code="REF456789"
    )
    db_session.add(master)
    await db_session.commit()
    
    repo = PromoCodeRepository(db_session)
    await repo.create_promo_code(
        code="VALID",
        type=PromoCodeType.PERCENT,
        discount_percent=10,
        max_uses=100
    )
    
    is_valid, error_msg, promo = await repo.validate_promo_code("VALID", master.id)
    
    assert is_valid is True
    assert error_msg is None
    assert promo is not None
    assert promo.code == "VALID"


@pytest.mark.asyncio
async def test_validate_promo_code_not_found(db_session):
    """Тест: промокод не найден"""
    repo = PromoCodeRepository(db_session)
    
    is_valid, error_msg, promo = await repo.validate_promo_code("NOTEXIST", 1)
    
    assert is_valid is False
    assert error_msg == "Промокод не найден"
    assert promo is None


@pytest.mark.asyncio
async def test_validate_promo_code_inactive(db_session):
    """Тест: промокод неактивен"""
    master = Master(telegram_id=123456789, phone="+79001234567", name="Test Master", referral_code="REF456789"
    )
    db_session.add(master)
    await db_session.commit()
    
    repo = PromoCodeRepository(db_session)
    promo = await repo.create_promo_code(
        code="INACTIVE",
        type=PromoCodeType.PERCENT,
        discount_percent=10
    )
    
    # Деактивируем промокод
    promo.status = PromoCodeStatus.INACTIVE
    await db_session.commit()
    
    is_valid, error_msg, _ = await repo.validate_promo_code("INACTIVE", master.id)
    
    assert is_valid is False
    assert error_msg == "Промокод неактивен"


@pytest.mark.asyncio
async def test_validate_promo_code_expired(db_session):
    """Тест: промокод истек"""
    master = Master(telegram_id=123456789, phone="+79001234567", name="Test Master", referral_code="REF456789"
    )
    db_session.add(master)
    await db_session.commit()
    
    repo = PromoCodeRepository(db_session)
    await repo.create_promo_code(
        code="EXPIRED",
        type=PromoCodeType.PERCENT,
        discount_percent=10,
        valid_until=datetime.utcnow() - timedelta(days=1)  # Истек вчера
    )
    
    is_valid, error_msg, _ = await repo.validate_promo_code("EXPIRED", master.id)
    
    assert is_valid is False
    assert error_msg == "Промокод истек"


@pytest.mark.asyncio
async def test_validate_promo_code_not_started(db_session):
    """Тест: промокод еще не действует"""
    master = Master(telegram_id=123456789, phone="+79001234567", name="Test Master", referral_code="REF456789"
    )
    db_session.add(master)
    await db_session.commit()
    
    repo = PromoCodeRepository(db_session)
    await repo.create_promo_code(
        code="FUTURE",
        type=PromoCodeType.PERCENT,
        discount_percent=10,
        valid_from=datetime.utcnow() + timedelta(days=1)  # Начнется завтра
    )
    
    is_valid, error_msg, _ = await repo.validate_promo_code("FUTURE", master.id)
    
    assert is_valid is False
    assert error_msg == "Промокод еще не действует"


@pytest.mark.asyncio
async def test_validate_promo_code_max_uses_reached(db_session):
    """Тест: превышен лимит использования"""
    master = Master(telegram_id=123456789, phone="+79001234567", name="Test Master", referral_code="REF456789"
    )
    db_session.add(master)
    await db_session.commit()
    
    repo = PromoCodeRepository(db_session)
    promo = await repo.create_promo_code(
        code="LIMITED",
        type=PromoCodeType.PERCENT,
        discount_percent=10,
        max_uses=5
    )
    
    # Устанавливаем счетчик на максимум
    promo.current_uses = 5
    await db_session.commit()
    
    is_valid, error_msg, _ = await repo.validate_promo_code("LIMITED", master.id)
    
    assert is_valid is False
    assert error_msg == "Промокод исчерпан"


@pytest.mark.asyncio
async def test_validate_promo_code_user_limit_reached(db_session):
    """Тест: пользователь уже использовал промокод"""
    master = Master(telegram_id=123456789, phone="+79001234567", name="Test Master", referral_code="REF456789"
    )
    db_session.add(master)
    await db_session.commit()
    
    repo = PromoCodeRepository(db_session)
    promo = await repo.create_promo_code(
        code="ONEPERUSER",
        type=PromoCodeType.PERCENT,
        discount_percent=10,
        max_uses_per_user=1
    )
    
    # Создаем использование
    usage = PromoCodeUsage(
        promo_code_id=promo.id,
        master_id=master.id,
        discount_amount=99,
        original_amount=990,
        final_amount=891
    )
    db_session.add(usage)
    await db_session.commit()
    
    is_valid, error_msg, _ = await repo.validate_promo_code("ONEPERUSER", master.id)
    
    assert is_valid is False
    assert error_msg == "Вы уже использовали этот промокод"


@pytest.mark.asyncio
async def test_apply_promo_code_percent(db_session):
    """Тест применения процентного промокода"""
    master = Master(telegram_id=123456789, phone="+79001234567", name="Test Master", referral_code="REF456789"
    )
    db_session.add(master)
    await db_session.commit()
    
    sub_repo = SubscriptionRepository(db_session)
    subscription = await sub_repo.create_subscription(
        master_id=master.id,
        plan='monthly',
        amount=990,
        duration_days=30
    )
    
    promo_repo = PromoCodeRepository(db_session)
    promo = await promo_repo.create_promo_code(
        code="PERCENT20",
        type=PromoCodeType.PERCENT,
        discount_percent=20
    )
    
    discount, final_amount = await promo_repo.apply_promo_code(
        promo_code=promo,
        master_id=master.id,
        subscription_id=subscription.id,
        original_amount=990
    )
    
    assert discount == 198  # 20% от 990
    assert final_amount == 792  # 990 - 198
    
    # Проверяем, что счетчик увеличился
    await db_session.refresh(promo)
    assert promo.current_uses == 1


@pytest.mark.asyncio
async def test_apply_promo_code_fixed(db_session):
    """Тест применения фиксированного промокода"""
    master = Master(telegram_id=123456789, phone="+79001234567", name="Test Master", referral_code="REF456789"
    )
    db_session.add(master)
    await db_session.commit()
    
    sub_repo = SubscriptionRepository(db_session)
    subscription = await sub_repo.create_subscription(
        master_id=master.id,
        plan='monthly',
        amount=990,
        duration_days=30
    )
    
    promo_repo = PromoCodeRepository(db_session)
    promo = await promo_repo.create_promo_code(
        code="FIXED100",
        type=PromoCodeType.FIXED,
        discount_amount=100
    )
    
    discount, final_amount = await promo_repo.apply_promo_code(
        promo_code=promo,
        master_id=master.id,
        subscription_id=subscription.id,
        original_amount=990
    )
    
    assert discount == 100
    assert final_amount == 890


@pytest.mark.asyncio
async def test_apply_promo_code_depletes(db_session):
    """Тест: промокод становится исчерпанным"""
    master = Master(telegram_id=123456789, phone="+79001234567", name="Test Master", referral_code="REF456789"
    )
    db_session.add(master)
    await db_session.commit()
    
    sub_repo = SubscriptionRepository(db_session)
    subscription = await sub_repo.create_subscription(
        master_id=master.id,
        plan='monthly',
        amount=990,
        duration_days=30
    )
    
    promo_repo = PromoCodeRepository(db_session)
    promo = await promo_repo.create_promo_code(
        code="LASTONE",
        type=PromoCodeType.PERCENT,
        discount_percent=10,
        max_uses=1  # Только одно использование
    )
    
    await promo_repo.apply_promo_code(
        promo_code=promo,
        master_id=master.id,
        subscription_id=subscription.id,
        original_amount=990
    )
    
    # Проверяем, что статус изменился на DEPLETED
    await db_session.refresh(promo)
    assert promo.status == PromoCodeStatus.DEPLETED
    assert promo.current_uses == 1


@pytest.mark.asyncio
async def test_get_promo_code_stats(db_session):
    """Тест получения статистики промокода"""
    master1 = Master(telegram_id=111, phone="+79001111111", name="Master 1", referral_code="REF111")
    master2 = Master(telegram_id=222, phone="+79002222222", name="Master 2", referral_code="REF222")
    db_session.add_all([master1, master2])
    await db_session.commit()
    
    promo_repo = PromoCodeRepository(db_session)
    promo = await promo_repo.create_promo_code(
        code="STATS",
        type=PromoCodeType.PERCENT,
        discount_percent=20,
        max_uses=100
    )
    
    sub_repo = SubscriptionRepository(db_session)
    
    # Два использования
    for master in [master1, master2]:
        subscription = await sub_repo.create_subscription(
            master_id=master.id,
            plan='monthly',
            amount=990,
            duration_days=30
        )
        await promo_repo.apply_promo_code(
            promo_code=promo,
            master_id=master.id,
            subscription_id=subscription.id,
            original_amount=990
        )
    
    stats = await promo_repo.get_promo_code_stats("STATS")
    
    assert stats['usage_count'] == 2
    assert stats['total_discount_given'] == 396  # 198 * 2
    assert stats['max_uses'] == 100
    assert stats['status'] == PromoCodeStatus.ACTIVE


@pytest.mark.asyncio
async def test_deactivate_promo_code(db_session):
    """Тест деактивации промокода"""
    repo = PromoCodeRepository(db_session)
    await repo.create_promo_code(
        code="DEACTIVATE",
        type=PromoCodeType.PERCENT,
        discount_percent=10
    )
    
    result = await repo.deactivate_promo_code("DEACTIVATE")
    
    assert result is True
    
    promo = await repo.get_promo_code("DEACTIVATE")
    assert promo.status == PromoCodeStatus.INACTIVE


@pytest.mark.asyncio
async def test_get_all_promo_codes(db_session):
    """Тест получения списка всех промокодов"""
    repo = PromoCodeRepository(db_session)
    
    # Создаем несколько промокодов
    await repo.create_promo_code(code="CODE1", type=PromoCodeType.PERCENT, discount_percent=10)
    await repo.create_promo_code(code="CODE2", type=PromoCodeType.FIXED, discount_amount=100)
    await repo.create_promo_code(code="CODE3", type=PromoCodeType.PERCENT, discount_percent=20)
    
    # Получаем все активные
    codes = await repo.get_all_promo_codes(status=PromoCodeStatus.ACTIVE)
    
    assert len(codes) == 3
    assert all(code.status == PromoCodeStatus.ACTIVE for code in codes)


@pytest.mark.asyncio
async def test_referral_promo_code(db_session):
    """Тест реферального промокода"""
    referrer = Master(telegram_id=111, phone="+79001111111", name="Referrer", referral_code="REF111")
    referred = Master(telegram_id=222, phone="+79002222222", name="Referred", referral_code="REF222")
    db_session.add_all([referrer, referred])
    await db_session.commit()
    
    repo = PromoCodeRepository(db_session)
    promo = await repo.create_promo_code(
        code="REFER10",
        type=PromoCodeType.PERCENT,
        discount_percent=10,
        is_referral=True,
        referrer_master_id=referrer.id,
        referrer_bonus_amount=100
    )
    
    assert promo.is_referral is True
    assert promo.referrer_master_id == referrer.id
    assert promo.referrer_bonus_amount == 100

