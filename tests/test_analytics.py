"""Tests for analytics service."""
import pytest
from datetime import datetime, timedelta

from services.analytics import AnalyticsService
from database.repositories import (
    MasterRepository, ServiceRepository, AppointmentRepository,
    SubscriptionRepository, ClientRepository
)
from database.models.appointment import AppointmentStatus
from database.models.subscription import SubscriptionStatus


@pytest.mark.asyncio
async def test_retention_empty_data(db_session):
    """Test retention report with no data."""
    analytics = AnalyticsService(db_session)
    
    retention = await analytics.get_retention_report()
    
    assert retention["day1"] == 0.0
    assert retention["day7"] == 0.0
    assert retention["day30"] == 0.0


@pytest.mark.asyncio
async def test_retention_calculation(db_session):
    """Test retention calculation with sample data."""
    master_repo = MasterRepository(db_session)
    client_repo = ClientRepository(db_session)
    appointment_repo = AppointmentRepository(db_session)
    service_repo = ServiceRepository(db_session)
    
    # Create masters registered 10 days ago
    now = datetime.utcnow()
    registration_date = now - timedelta(days=10)
    
    # Master 1: active on day 1, 7
    master1 = await master_repo.create(
        telegram_id=111111,
        name="Master 1",
        telegram_username="master1"
    )
    master1.created_at = registration_date
    
    # Master 2: active on day 1 only
    master2 = await master_repo.create(
        telegram_id=222222,
        name="Master 2",
        telegram_username="master2"
    )
    master2.created_at = registration_date
    
    # Master 3: not active
    master3 = await master_repo.create(
        telegram_id=333333,
        name="Master 3",
        telegram_username="master3"
    )
    master3.created_at = registration_date
    
    await db_session.commit()
    
    # Create clients
    client1 = await client_repo.create(
        master_id=master1.id,
        telegram_id=444444,
        name="Client 1"
    )
    client2 = await client_repo.create(
        master_id=master2.id,
        telegram_id=555555,
        name="Client 2"
    )
    
    # Create services
    service1 = await service_repo.create(
        master_id=master1.id,
        name="Service 1",
        duration_minutes=60,
        price=1000
    )
    service2 = await service_repo.create(
        master_id=master2.id,
        name="Service 2",
        duration_minutes=60,
        price=1000
    )
    
    # Create appointments for activity tracking
    # Master 1: day 1 and day 7
    day1 = registration_date + timedelta(days=1)
    day7 = registration_date + timedelta(days=7)
    
    await appointment_repo.create(
        master_id=master1.id,
        client_id=client1.id,
        service_id=service1.id,
        start_time=day1 + timedelta(hours=10),
        end_time=day1 + timedelta(hours=11)
    )
    
    await appointment_repo.create(
        master_id=master1.id,
        client_id=client1.id,
        service_id=service1.id,
        start_time=day7 + timedelta(hours=10),
        end_time=day7 + timedelta(hours=11)
    )
    
    # Master 2: day 1 only
    await appointment_repo.create(
        master_id=master2.id,
        client_id=client2.id,
        service_id=service2.id,
        start_time=day1 + timedelta(hours=14),
        end_time=day1 + timedelta(hours=15)
    )
    
    await db_session.commit()
    
    # Calculate retention
    analytics = AnalyticsService(db_session)
    retention = await analytics.get_retention_report(
        start_date=registration_date - timedelta(days=1),
        end_date=registration_date + timedelta(days=1)
    )
    
    # Day 1: 2 out of 3 active = 66.7%
    assert retention["day1"] >= 60.0 and retention["day1"] <= 70.0
    
    # Day 7: 1 out of 3 active = 33.3%
    assert retention["day7"] >= 30.0 and retention["day7"] <= 40.0


@pytest.mark.asyncio
async def test_cohort_analysis_empty(db_session):
    """Test cohort analysis with no data."""
    analytics = AnalyticsService(db_session)
    
    cohorts = await analytics.get_cohort_analysis(cohort_weeks=4)
    
    # Should return empty list or cohorts with 0 registered
    assert isinstance(cohorts, list)


@pytest.mark.asyncio
async def test_cohort_analysis_grouping(db_session):
    """Test cohort grouping by week."""
    master_repo = MasterRepository(db_session)
    
    now = datetime.utcnow()
    
    # Create masters in different weeks
    # Week 1
    for i in range(3):
        master = await master_repo.create(
            telegram_id=1000 + i,
            name=f"Master Week1 {i}",
            telegram_username=f"master_w1_{i}"
        )
        master.created_at = now - timedelta(weeks=1, days=i)
    
    # Week 2
    for i in range(5):
        master = await master_repo.create(
            telegram_id=2000 + i,
            name=f"Master Week2 {i}",
            telegram_username=f"master_w2_{i}"
        )
        master.created_at = now - timedelta(weeks=2, days=i)
    
    await db_session.commit()
    
    # Analyze cohorts
    analytics = AnalyticsService(db_session)
    cohorts = await analytics.get_cohort_analysis(cohort_weeks=3)
    
    # Should have cohort data
    assert len(cohorts) >= 2
    
    # Check structure
    for cohort in cohorts:
        assert "cohort_week" in cohort
        assert "registered" in cohort
        assert "day0" in cohort
        assert cohort["day0"] == 100.0  # All users active on day 0


@pytest.mark.asyncio
async def test_funnel_conversion_empty(db_session):
    """Test funnel conversion with no data."""
    analytics = AnalyticsService(db_session)
    
    funnel = await analytics.get_funnel_conversion()
    
    assert funnel["registered"]["count"] == 0
    assert funnel["registered"]["rate"] == 100.0
    assert funnel["onboarded"]["count"] == 0
    assert funnel["paid"]["count"] == 0


@pytest.mark.asyncio
async def test_funnel_conversion_calculation(db_session):
    """Test funnel conversion rates."""
    master_repo = MasterRepository(db_session)
    service_repo = ServiceRepository(db_session)
    appointment_repo = AppointmentRepository(db_session)
    subscription_repo = SubscriptionRepository(db_session)
    
    # Create 10 registered masters
    masters = []
    for i in range(10):
        master = await master_repo.create(
            telegram_id=10000 + i,
            name=f"Master {i}",
            telegram_username=f"master_{i}"
        )
        masters.append(master)
    
    await db_session.commit()
    
    # 8 completed onboarding
    for i in range(8):
        masters[i].is_onboarded = True
    
    # 6 created services
    for i in range(6):
        await service_repo.create(
            master_id=masters[i].id,
            name=f"Service {i}",
            duration_minutes=60,
            price=1000
        )
    
    await db_session.commit()
    
    # 4 received bookings
    services = await service_repo.get_all_by_master(masters[0].id)
    for i in range(4):
        # Create a client first
        await appointment_repo.create(
            master_id=masters[i].id,
            client_id=1000 + i,
            service_id=services[0].id if services else 1,
            start_time=datetime.utcnow() + timedelta(days=1),
            end_time=datetime.utcnow() + timedelta(days=1, hours=1)
        )
    
    # 3 paid for subscription
    for i in range(3):
        await subscription_repo.create(
            master_id=masters[i].id,
            plan="monthly",
            status=SubscriptionStatus.ACTIVE,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30)
        )
    
    await db_session.commit()
    
    # Calculate funnel
    analytics = AnalyticsService(db_session)
    funnel = await analytics.get_funnel_conversion()
    
    assert funnel["registered"]["count"] == 10
    assert funnel["registered"]["rate"] == 100.0
    
    assert funnel["onboarded"]["count"] == 8
    assert funnel["onboarded"]["rate"] == 80.0
    
    assert funnel["first_service"]["count"] == 6
    assert funnel["first_service"]["rate"] == 60.0


@pytest.mark.asyncio
async def test_growth_metrics_empty(db_session):
    """Test growth metrics with no data."""
    analytics = AnalyticsService(db_session)
    
    growth = await analytics.get_growth_metrics(period='month')
    
    assert growth["dau"] == 0
    assert growth["wau"] == 0
    assert growth["mau"] == 0
    assert growth["activation_rate"] == 0.0


@pytest.mark.asyncio
async def test_growth_metrics_dau_calculation(db_session):
    """Test DAU calculation."""
    master_repo = MasterRepository(db_session)
    service_repo = ServiceRepository(db_session)
    appointment_repo = AppointmentRepository(db_session)
    
    # Create masters
    masters = []
    for i in range(5):
        master = await master_repo.create(
            telegram_id=20000 + i,
            name=f"Master {i}",
            telegram_username=f"master_{i}"
        )
        masters.append(master)
        
        # Create service
        service = await service_repo.create(
            master_id=master.id,
            name=f"Service {i}",
            duration_minutes=60,
            price=1000
        )
        
        # Create appointment today
        today = datetime.utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
        await appointment_repo.create(
            master_id=master.id,
            client_id=100 + i,
            service_id=service.id,
            start_time=today,
            end_time=today + timedelta(hours=1)
        )
    
    await db_session.commit()
    
    # Calculate growth
    analytics = AnalyticsService(db_session)
    growth = await analytics.get_growth_metrics()
    
    # Should have 5 active users today
    assert growth["dau"] == 5


@pytest.mark.asyncio
async def test_growth_metrics_activation_rate(db_session):
    """Test activation rate calculation."""
    master_repo = MasterRepository(db_session)
    
    # Create 10 masters
    for i in range(10):
        master = await master_repo.create(
            telegram_id=30000 + i,
            name=f"Master {i}",
            telegram_username=f"master_{i}"
        )
        
        # 7 completed onboarding
        if i < 7:
            master.is_onboarded = True
    
    await db_session.commit()
    
    # Calculate growth
    analytics = AnalyticsService(db_session)
    growth = await analytics.get_growth_metrics()
    
    # Activation rate should be 70%
    assert growth["activation_rate"] == 70.0


@pytest.mark.asyncio
async def test_growth_metrics_periods(db_session):
    """Test growth metrics for different periods."""
    analytics = AnalyticsService(db_session)
    
    # Test different periods don't crash
    for period in ['day', 'week', 'month']:
        growth = await analytics.get_growth_metrics(period=period)
        assert "period" in growth
        assert growth["period"] == period
