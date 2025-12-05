"""
REST API endpoints for WebApp.

This module contains all aiohttp routes for client and master WebApps.
All endpoints are extracted from the monolithic main.py for better modularity.
"""

import logging
from datetime import datetime, timedelta, timezone
from aiohttp import web
from pytz import timezone as pytz_timezone
from sqlalchemy import select, and_, or_, func

from database import async_session_maker
from database.repositories import (
    MasterRepository, ServiceRepository, ClientRepository,
    AppointmentRepository, ReminderRepository, ExpenseRepository
)
from database.models import Service, AppointmentStatus
from database.models.appointment import Appointment
from database.models.client import Client
from bot.utils.time_utils import generate_half_hour_slots, parse_work_schedule
from bot.config import settings
from services.scheduler import create_appointment_reminders

logger = logging.getLogger(__name__)

# Bot instance will be set by main.py
bot = None


def set_bot_instance(bot_instance):
    """Set bot instance for notifications."""
    global bot
    bot = bot_instance


def setup_routes(app: web.Application):
    """
    Setup all API routes.
    
    Args:
        app: aiohttp Application instance
    """
    # Health check
    app.router.add_get('/health', health_check)
    
    # Client API
    app.router.add_get('/api/services', get_services)
    app.router.add_get('/api/client/info', get_client_info)
    app.router.add_get('/api/slots', get_slots)
    app.router.add_post('/api/book', book_appointment)
    app.router.add_get('/api/client/appointments', get_client_appointments)
    app.router.add_post('/api/client/appointment/cancel', cancel_appointment_client)
    app.router.add_post('/api/client/appointment/reschedule', reschedule_appointment_client)
    
    # Master API - Appointments
    app.router.add_get('/api/master/appointments', get_master_appointments)
    app.router.add_get('/api/master/schedule', get_master_schedule)
    app.router.add_post('/api/master/schedule/days_off', set_master_days_off)
    app.router.add_post('/api/master/schedule/hours', set_master_hours)
    app.router.add_post('/api/master/appointment/complete', complete_appointment)
    app.router.add_post('/api/master/appointment/cancel', cancel_appointment_master)
    app.router.add_post('/api/master/appointment/reschedule', reschedule_appointment_master)
    
    # Master API - Clients
    app.router.add_get('/api/master/clients', get_master_clients)
    app.router.add_get('/api/master/client/history', get_client_history)
    
    # Master API - Services
    app.router.add_get('/api/master/services', get_master_services)
    app.router.add_post('/api/master/service/save', save_master_service)
    app.router.add_post('/api/master/service/delete', delete_master_service)
    
    # Master API - Financial
    app.router.add_get('/api/master/analytics/financial', get_financial_analytics)
    app.router.add_get('/api/master/expenses', get_expenses)
    app.router.add_post('/api/master/expense/create', create_expense)
    app.router.add_post('/api/master/expense/update', update_expense)
    app.router.add_post('/api/master/expense/delete', delete_expense)


# ========== Health Check ==========

async def health_check(request: web.Request):
    """Health check endpoint."""
    return web.json_response({
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat()
    })
