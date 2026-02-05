"""
Main entry point for BeautyAssist bot.

This is the orchestration layer that:
1. Initializes the bot and database
2. Registers handlers and middleware
3. Starts the web server (API + static files)
4. Starts background tasks (reminders, notifications)
5. Runs the bot polling loop
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiohttp import web

from bot.config import settings
from database.base import init_db
from bot.logging_config import setup_logging

# Setup logging first
setup_logging()
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(
    token=settings.bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()


def register_middlewares():
    """Register all middleware in correct order."""
    from bot.middlewares import setup_middlewares
    setup_middlewares(dp)
    logger.info("Middlewares registered")


def register_handlers():
    """Register all bot handlers."""
    # Import handler registration functions
    from bot.handlers import onboarding, master, appointments, admin, subscription, referral, admin_payouts, support, export
    from bot.handlers import api as api_handlers
    from bot.handlers import yookassa_handlers
    from bot.middlewares.admin import AdminOnlyMiddleware
    
    # Inject bot instance into handlers that need it
    onboarding.inject_bot(bot)
    master.inject_bot(bot)
    appointments.inject_bot(bot)
    api_handlers.inject_bot(bot)
    
    # Register admin handlers FIRST with AdminOnlyMiddleware
    # AdminOnlyMiddleware должен быть ПЕРЕД AuthMiddleware
    admin.router.message.middleware(AdminOnlyMiddleware())
    admin.router.callback_query.middleware(AdminOnlyMiddleware())
    dp.include_router(admin.router)
    
    # Register admin_payouts handlers with AdminOnlyMiddleware
    admin_payouts.router.message.middleware(AdminOnlyMiddleware())
    dp.include_router(admin_payouts.router)
    
    # Register subscription handlers (before SubscriptionMiddleware)
    dp.include_router(subscription.router)
    
    # Register referral handlers
    dp.include_router(referral.router)
    
    # Register support handlers
    dp.include_router(support.router)
    
    # Register YooKassa payment handlers
    dp.include_router(yookassa_handlers.router)
    
    # Register export handlers (must be after subscription middleware)
    dp.include_router(export.router)
    
    # Then register other handlers (they will use AuthMiddleware and SubscriptionMiddleware from global setup)
    onboarding.register_handlers(dp)
    master.register_handlers(dp)
    appointments.register_handlers(dp)
    
    logger.info("Handlers registered")


def register_api_routes():
    """Register API routes and return the application."""
    from bot.handlers import api as api_handlers
    from bot.handlers.api_yookassa import setup_yookassa_routes
    from bot.middlewares.admin_api import admin_api_auth_middleware
    from aiohttp import web
    
    # Middleware to handle ngrok browser warning
    @web.middleware
    async def ngrok_middleware(request, handler):
        """Add headers to bypass ngrok browser warning."""
        response = await handler(request)
        # Add CORS headers for Telegram WebApp
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = '*'
        return response
    
    # Create app with middlewares (order matters: ngrok first, then admin auth)
    app = web.Application(middlewares=[ngrok_middleware, admin_api_auth_middleware])
    api_handlers.setup_routes(app)
    
    # Setup YooKassa webhook routes
    setup_yookassa_routes(app)
    
    # Static webapp files with cache busting
    import time
    cache_bust = str(int(time.time()))
    app.router.add_static('/webapp', path='webapp', name='webapp', append_version=True)
    app.router.add_static('/webapp-master', path='webapp-master', name='webapp-master', append_version=True)
    
    logger.info("API routes and static files registered")
    return app


def start_background_tasks():
    """Start background scheduler for reminders and notifications."""
    from services.reminder_tasks import inject_bot, start_reminder_scheduler
    inject_bot(bot)
    start_reminder_scheduler()
    logger.info("Background tasks started")


async def setup_bot_commands():
    """Setup bot commands menu for all users."""
    from aiogram.types import BotCommand, BotCommandScopeDefault, MenuButtonCommands
    
    # Commands for masters (default scope)
    commands = [
        BotCommand(command="menu", description="📋 Главное меню"),
        BotCommand(command="services", description="💅 Мои услуги"),
        BotCommand(command="appointments", description="📅 Записи"),
        BotCommand(command="clients", description="👥 Клиенты"),
        BotCommand(command="schedule", description="🕐 График работы"),
        BotCommand(command="city", description="🌍 Город/Таймзона"),
        BotCommand(command="qr_code", description="📱 QR-код для записи"),
        BotCommand(command="subscription", description="💳 Подписка"),
        BotCommand(command="referral", description="🎁 Реферальная программа"),
        BotCommand(command="support", description="💬 Поддержка"),
    ]
    
    await bot.set_my_commands(commands=commands, scope=BotCommandScopeDefault())
    
    # Set default menu button to show commands (this makes ☰ button visible)
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    
    logger.info("Bot commands menu configured")


async def main():
    """Main entry point."""
    logger.info("Starting BeautyAssist bot...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Register middlewares
    register_middlewares()
    
    # Register bot handlers
    register_handlers()
    
    # Setup bot commands menu
    await setup_bot_commands()
    
    # Create and start web server
    app = register_api_routes()
    runner = web.AppRunner(app)
    await runner.setup()
    # Bind to localhost only for security - nginx will proxy external requests
    site = web.TCPSite(runner, '127.0.0.1', 8080)
    await site.start()
    logger.info("Web server started on 127.0.0.1:8080 (localhost only)")
    
    # Start background tasks
    start_background_tasks()
    
    # Start bot polling
    logger.info("Starting bot polling...")
    try:
        await dp.start_polling(bot)
    finally:
        logger.info("Bot stopped")
        await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
