"""Subscription plans configuration."""
from dataclasses import dataclass
from datetime import timedelta

from database.models.subscription import SubscriptionPlan


@dataclass
class PlanConfig:
    """Subscription plan configuration."""
    
    plan: SubscriptionPlan
    name: str
    description: str
    duration_days: int
    price_rub: int
    price_stars: int  # Telegram Stars (1 star ≈ 1 RUB)
    features: list[str]
    is_trial: bool = False
    
    @property
    def duration(self) -> timedelta:
        """Get duration as timedelta."""
        return timedelta(days=self.duration_days)
    
    @property
    def price_per_month_rub(self) -> int:
        """Calculate price per month in RUB."""
        months = self.duration_days / 30
        return int(self.price_rub / months)


# Subscription plans configuration
SUBSCRIPTION_PLANS = {
    SubscriptionPlan.TRIAL: PlanConfig(
        plan=SubscriptionPlan.TRIAL,
        name="Пробный период",
        description="30 дней бесплатно",
        duration_days=30,
        price_rub=0,
        price_stars=0,
        is_trial=True,
        features=[
            "✅ Все функции бота",
            "✅ Неограниченное количество записей",
            "✅ Напоминания клиентам",
            "✅ Финансовая аналитика",
            "⏰ 30 дней доступа",
        ],
    ),
    SubscriptionPlan.MONTHLY: PlanConfig(
        plan=SubscriptionPlan.MONTHLY,
        name="Месячная подписка",
        description="Оплата каждый месяц",
        duration_days=30,
        price_rub=790,
        price_stars=390,  # 790₽ ≈ 390 звёзд (курс ~2₽/⭐)
        features=[
            "✅ Все функции бота",
            "✅ Неограниченное количество записей",
            "✅ Напоминания клиентам",
            "✅ Финансовая аналитика",
            "✅ Поддержка 24/7",
            "💰 390⭐ (790₽/мес)",
        ],
    ),
    SubscriptionPlan.QUARTERLY: PlanConfig(
        plan=SubscriptionPlan.QUARTERLY,
        name="3 месяца",
        description="Экономия 15%",
        duration_days=90,
        price_rub=2015,  # ~672₽/мес
        price_stars=995,  # 2015₽ ≈ 995⭐ (экономия 15%)
        features=[
            "✅ Все функции бота",
            "✅ Неограниченное количество записей",
            "✅ Напоминания клиентам",
            "✅ Финансовая аналитика",
            "✅ Поддержка 24/7",
            "🎁 Экономия 15%",
            "💰 995⭐ (2015₽, 332⭐/мес)",
        ],
    ),
    SubscriptionPlan.YEARLY: PlanConfig(
        plan=SubscriptionPlan.YEARLY,
        name="Годовая подписка",
        description="Экономия 30%",
        duration_days=365,
        price_rub=6636,  # ~553₽/мес
        price_stars=3276,  # 6636₽ ≈ 3276⭐ (экономия 30%)
        features=[
            "✅ Все функции бота",
            "✅ Неограниченное количество записей",
            "✅ Напоминания клиентам",
            "✅ Финансовая аналитика",
            "✅ Приоритетная поддержка",
            "✅ Ранний доступ к новым функциям",
            "🎁 Экономия 30%",
            "💰 3276⭐ (6636₽, 273⭐/мес)",
        ],
    ),
}


def get_plan_config(plan: SubscriptionPlan) -> PlanConfig:
    """Get configuration for subscription plan."""
    return SUBSCRIPTION_PLANS[plan]


def format_plan_info(plan: SubscriptionPlan) -> str:
    """Format plan information for display."""
    config = get_plan_config(plan)
    
    text = f"<b>{config.name}</b>\n"
    text += f"{config.description}\n\n"
    
    for feature in config.features:
        text += f"{feature}\n"
    
    return text


def get_available_plans(exclude_trial: bool = False) -> list[PlanConfig]:
    """Get list of available plans."""
    plans = list(SUBSCRIPTION_PLANS.values())
    
    if exclude_trial:
        plans = [p for p in plans if not p.is_trial]
    
    return plans
