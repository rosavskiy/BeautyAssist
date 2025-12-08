"""Configuration management using pydantic-settings."""
import os
from typing import Any
from pydantic import Field, PostgresDsn, AnyUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Environment
    environment: str = Field(
        default_factory=lambda: os.getenv("ENVIRONMENT", "development"),
        description="Environment: development, staging, production"
    )
    
    # Telegram Bot
    bot_token: str = Field(..., description="Telegram Bot API Token")
    bot_username: str = Field(..., description="Telegram Bot Username (without @)")
    webhook_url: str | None = Field(None, description="Webhook URL for production")
    webhook_path: str = Field("/webhook", description="Webhook path")
    webapp_base_url: AnyUrl | None = Field(None, description="Base URL to host Telegram WebApp")
    
    # Database
    database_url: PostgresDsn = Field(..., description="PostgreSQL connection URL")
    database_pool_size: int = Field(10, description="Connection pool size")
    database_max_overflow: int = Field(20, description="Max overflow connections")
    
    # Redis
    redis_url: str = Field("redis://localhost:6379/0", description="Redis connection URL")
    
    # Application
    timezone: str = Field("Europe/Moscow", description="Default timezone")
    debug: bool = Field(False, description="Debug mode")
    log_level: str = Field("INFO", description="Logging level")
    
    # Admin (can be comma-separated string or list)
    admin_telegram_ids: str | list[int] = Field(
        default="",
        description="Admin Telegram IDs (comma-separated in env)"
    )
    
    # Support
    support_admin_id: int | None = Field(
        None,
        description="Telegram ID of support admin who receives support requests"
    )
    
    @field_validator("admin_telegram_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: Any) -> list[int]:
        """Parse admin telegram IDs from string or list."""
        if isinstance(v, list):
            return [int(x) for x in v]
        if isinstance(v, str):
            if not v or not v.strip():
                return []
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, int):
            return [v]
        return []
    
    # Features
    enable_sms_notifications: bool = Field(False, description="Enable SMS notifications")
    sms_provider_api_key: str | None = Field(None, description="SMS provider API key")
    sms_provider_url: str | None = Field(None, description="SMS provider URL")
    
    # Freemium Limits
    free_max_clients: int = Field(200, description="Max clients for free plan")
    free_max_services: int = Field(20, description="Max services for free plan")
    free_max_appointments_per_month: int = Field(15, description="Max appointments per month for free")
    
    # Payment providers
    yookassa_shop_id: str | None = Field(None, description="YooKassa shop ID")
    yookassa_secret_key: str | None = Field(None, description="YooKassa secret key")
    yookassa_return_url: str | None = Field(None, description="YooKassa return URL after payment")


# Global settings instance
settings = Settings()

# Bot username constant for referral links
BOT_USERNAME = settings.bot_username

# City to timezone mapping
CITY_TZ_MAP = {
    "Москва": "Europe/Moscow",
    "Санкт-Петербург": "Europe/Moscow",
    "Екатеринбург": "Asia/Yekaterinburg",
    "Новосибирск": "Asia/Novosibirsk",
    "Красноярск": "Asia/Krasnoyarsk",
    "Владивосток": "Asia/Vladivostok",
    "Самара": "Europe/Samara",
    "Саратов": "Europe/Saratov",
}
