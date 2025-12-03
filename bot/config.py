"""Configuration management using pydantic-settings."""
from pydantic import Field, PostgresDsn, AnyUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
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
    
    # Features
    enable_sms_notifications: bool = Field(False, description="Enable SMS notifications")
    sms_provider_api_key: str | None = Field(None, description="SMS provider API key")
    sms_provider_url: str | None = Field(None, description="SMS provider URL")
    
    # Freemium Limits
    free_max_clients: int = Field(200, description="Max clients for free plan")
    free_max_services: int = Field(20, description="Max services for free plan")
    free_max_appointments_per_month: int = Field(15, description="Max appointments per month for free")
    
    # Payment (future)
    payment_provider: str | None = Field(None, description="Payment provider name")
    payment_api_key: str | None = Field(None, description="Payment API key")
    subscription_price_rub: int = Field(490, description="Subscription price in RUB")


# Global settings instance
settings = Settings()
