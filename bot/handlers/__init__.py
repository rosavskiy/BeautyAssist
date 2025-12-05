"""
Handlers package initialization.

This package contains all Telegram bot handlers organized by functionality:
- onboarding.py: Initial setup process for new masters and client booking
- master.py: Commands and functionality for masters
- appointments.py: Appointment management and callbacks
- api.py: REST API endpoints (aiohttp)
"""

from aiogram import Dispatcher


def register_all_handlers(dp: Dispatcher):
    """
    Register all bot handlers.
    
    Order matters! More specific handlers should be registered first.
    
    Args:
        dp: Aiogram Dispatcher instance
    """
    # Import handlers here to avoid circular imports
    from . import onboarding, master, appointments, referral
    
    # Register in order (most specific first)
    onboarding.register_handlers(dp)
    master.register_handlers(dp)
    appointments.register_handlers(dp)
    referral.register_handlers(dp)


__all__ = ['register_all_handlers', 'onboarding', 'master', 'appointments', 'api']
