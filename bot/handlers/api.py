"""
REST API endpoints for WebApp - COMPLETE VERSION.

This file will replace api.py after verification.
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
from services.analytics import AnalyticsService

logger = logging.getLogger(__name__)

# Bot instance will be set by main.py
bot = None


def set_bot_instance(bot_instance):
    """Set bot instance for notifications."""
    global bot
    bot = bot_instance


# Alias for consistency with other handlers
inject_bot = set_bot_instance


def setup_routes(app: web.Application):
    """Setup all API routes."""
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
    
    # Admin API - Analytics
    app.router.add_get('/api/admin/analytics/retention', get_retention_analytics)
    app.router.add_get('/api/admin/analytics/cohorts', get_cohort_analytics)
    app.router.add_get('/api/admin/analytics/funnel', get_funnel_analytics)
    app.router.add_get('/api/admin/analytics/growth', get_growth_analytics)


# ========== Health Check ==========

async def health_check(request: web.Request):
    """Health check endpoint."""
    return web.json_response({
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat()
    })


# ========== Client API ==========

async def get_services(request: web.Request):
    """Get list of active services for a master."""
    code = request.query.get("code")
    if not code:
        return web.json_response({"error": "code is required"}, status=400)
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        srepo = ServiceRepository(session)
        master = await mrepo.get_by_referral_code(code)
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        services = await srepo.get_all_by_master(master.id, active_only=True)
        return web.json_response([
            {
                "id": s.id, 
                "name": s.name, 
                "price": s.price, 
                "duration": s.duration_minutes,
                "category": s.category
            }
            for s in services
        ])


async def get_client_info(request: web.Request):
    """Get client info by telegram_id to prefill booking form."""
    code = request.query.get("code")
    telegram_id_s = request.query.get("telegram_id")
    
    if not code or not telegram_id_s:
        return web.json_response({"error": "code and telegram_id required"}, status=400)
    
    try:
        telegram_id = int(telegram_id_s)
    except ValueError:
        return web.json_response({"error": "invalid telegram_id"}, status=400)
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        crepo = ClientRepository(session)
        
        master = await mrepo.get_by_referral_code(code)
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        result = await session.execute(
            select(Client).where(
                Client.master_id == master.id,
                Client.telegram_id == telegram_id
            ).limit(1)
        )
        client = result.scalar_one_or_none()
        
        if not client:
            return web.json_response({"found": False})
        
        return web.json_response({
            "found": True,
            "name": client.name,
            "phone": client.phone,
            "telegram_username": client.telegram_username
        })


async def get_slots(request: web.Request):
    """Get available time slots for a service on a specific date."""
    code = request.query.get("code")
    service_id_s = request.query.get("service")
    date_s = request.query.get("date")
    
    if not (code and service_id_s and date_s):
        return web.json_response({"error": "code, service, date required"}, status=400)
    
    try:
        service_id = int(service_id_s)
        date = datetime.strptime(date_s, "%Y-%m-%d")
    except ValueError:
        return web.json_response({"error": "bad params"}, status=400)
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        srepo = ServiceRepository(session)
        arepo = AppointmentRepository(session)
        
        master = await mrepo.get_by_referral_code(code)
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        service = await srepo.get_by_id(service_id)
        if not service or service.master_id != master.id:
            return web.json_response({"error": "service not found"}, status=404)
        
        tz = pytz_timezone(master.timezone or "Europe/Moscow")
        
        # Check if date is in days_off_dates
        ws = master.work_schedule or {}
        days_off_dates = set(ws.get("days_off_dates", []))
        if date_s in days_off_dates:
            return web.json_response([])
        
        # Get schedule for that date
        intervals = parse_work_schedule(master.work_schedule or {}, date)
        if not intervals:
            return web.json_response([])
        
        # Get existing appointments that day
        start_day = datetime(date.year, date.month, date.day)
        end_day = start_day + timedelta(days=1)
        existing = await arepo.get_by_master(master.id, start_date=start_day, end_date=end_day)
        busy = [(a.start_time, a.end_time) for a in existing 
                if a.status in (AppointmentStatus.SCHEDULED.value, AppointmentStatus.CONFIRMED.value)]
        
        # Helper: normalize to timezone-aware UTC
        def to_aware_utc(dt: datetime) -> datetime:
            if dt.tzinfo is None:
                local_dt = tz.localize(dt)
                return local_dt.astimezone(timezone.utc)
            return dt.astimezone(timezone.utc)
        
        # Generate slots
        slots = []
        busy_utc = [(to_aware_utc(b_start), to_aware_utc(b_end)) for b_start, b_end in busy]
        
        for start_t, end_t in intervals:
            starts = generate_half_hour_slots(start_t, end_t, start_day)
            for st in starts:
                et = st + timedelta(minutes=service.duration_minutes)
                
                # Ensure service fits within working interval
                interval_end_dt = datetime.combine(start_day.date(), end_t)
                if et > interval_end_dt:
                    st_utc = to_aware_utc(st)
                    available = st_utc > datetime.now(timezone.utc)
                    slots.append({"start": st, "end": et, "available": False if available else False})
                    continue
                
                st_utc = to_aware_utc(st)
                et_utc = to_aware_utc(et)
                conflict = any((st_utc < b_end and et_utc > b_start) for b_start, b_end in busy_utc)
                available = (not conflict) and (st_utc > datetime.now(timezone.utc))
                slots.append({"start": st, "end": et, "available": available})
        
        # Limit to first 48 half-hour slots
        slots = slots[:48]
        return web.json_response([
            {"start": s["start"].isoformat(), "end": s["end"].isoformat(), "available": s["available"]}
            for s in slots
        ])


async def book_appointment(request: web.Request):
    """Create a new appointment booking."""
    payload = await request.json()
    code = payload.get("code")
    service_id = payload.get("service")
    start_iso = payload.get("start")
    name = (payload.get("name") or "Клиент").strip()
    phone = (payload.get("phone") or "").strip()
    tg_id = payload.get("telegram_id")
    tg_username = payload.get("telegram_username")
    client_comment = (payload.get("client_comment") or "").strip()
    
    if not all([code, service_id, start_iso, name, phone]):
        return web.json_response({"error": "missing fields"}, status=400)
    
    # Validate phone format
    if not isinstance(phone, str) or not phone.startswith('+7') or len(phone) != 12 or not phone[2:].isdigit():
        return web.json_response({"error": "bad_phone"}, status=400)
    
    try:
        service_id = int(service_id)
        start_dt = datetime.fromisoformat(start_iso)
    except Exception:
        return web.json_response({"error": "bad fields"}, status=400)
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        srepo = ServiceRepository(session)
        crepo = ClientRepository(session)
        arepo = AppointmentRepository(session)
        
        master = await mrepo.get_by_referral_code(code)
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        service = await srepo.get_by_id(service_id)
        if not service or service.master_id != master.id:
            return web.json_response({"error": "service not found"}, status=404)
        
        # Normalize time to UTC
        try:
            tz = pytz_timezone(master.timezone or "Europe/Moscow")
            if start_dt.tzinfo is None:
                local_dt = tz.localize(start_dt)
                start_dt = local_dt.astimezone(timezone.utc)
            else:
                start_dt = start_dt.astimezone(timezone.utc)
        except Exception:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        
        end_dt = start_dt + timedelta(minutes=service.duration_minutes)
        
        # Check conflict
        conflict = await arepo.check_time_conflict(master.id, start_dt, end_dt)
        if conflict:
            return web.json_response({"error": "conflict"}, status=409)
        
        # Create/find client
        client = await crepo.get_by_phone(master.id, phone)
        if not client:
            client = await crepo.create(master.id, name=name, phone=phone)
        
        # Update Telegram info
        updated = False
        if tg_id:
            try:
                tg_id_int = int(tg_id)
                if client.telegram_id != tg_id_int:
                    client.telegram_id = tg_id_int
                    updated = True
            except Exception:
                pass
        
        if tg_username:
            tg_username_str = str(tg_username).strip()
            if tg_username_str and client.telegram_username != tg_username_str:
                client.telegram_username = tg_username_str
                updated = True
        
        if name and client.name != name:
            client.name = name
            updated = True
        
        if updated:
            await crepo.update(client)
        
        # Create appointment
        app = await arepo.create(master.id, client.id, service.id, start_dt, end_dt)
        if client_comment:
            app.client_comment = client_comment
        await session.flush()
        
        # Create reminders
        try:
            await create_appointment_reminders(session, app, cancel_existing=False)
        except Exception:
            pass
        
        await session.commit()
        
        # Notify master
        try:
            tz_name = master.timezone or "Europe/Moscow"
            tz = pytz_timezone(tz_name)
            local_start = start_dt.replace(tzinfo=timezone.utc).astimezone(tz)
            when_str = local_start.strftime('%d.%m.%Y %H:%M')
            
            client_link = ""
            if client.telegram_username:
                safe_username = client.telegram_username.strip()
                if safe_username:
                    client_link = f" <a href=\"https://t.me/{safe_username}\">@{safe_username}</a>"
            elif client.telegram_id:
                client_link = f" <a href=\"tg://user?id={client.telegram_id}\">ID:{client.telegram_id}</a>"
            
            text = (
                f"🆕 Новая запись\n\n"
                f"Клиент: {client.name}{client_link}\n"
                f"Телефон: {client.phone}\n"
                f"Услуга: {service.name}\n"
                f"Время: {when_str} ({tz_name})"
            )
            if client_comment:
                text += f"\n💬 Комментарий: {client_comment}"
            
            await bot.send_message(master.telegram_id, text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Failed to notify master: {e}")
        
        return web.json_response({"ok": True, "appointment_id": app.id})


async def get_client_appointments(request: web.Request):
    """Get appointments for a client."""
    code = request.query.get("code")
    telegram_id = request.query.get("telegram_id")
    status_filter = request.query.get("status")
    
    if not code or not telegram_id:
        return web.json_response({"error": "code and telegram_id required"}, status=400)
    
    try:
        telegram_id = int(telegram_id)
    except Exception:
        return web.json_response({"error": "invalid telegram_id"}, status=400)
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        crepo = ClientRepository(session)
        srepo = ServiceRepository(session)
        
        master = await mrepo.get_by_referral_code(code)
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        client = await crepo.get_by_telegram_id(master.id, telegram_id)
        if not client:
            return web.json_response({"appointments": []})
        
        now = datetime.now(timezone.utc)
        
        # Build query based on status filter
        conditions = [Appointment.client_id == client.id]
        
        if status_filter == "upcoming":
            conditions.append(Appointment.start_time >= now)
            conditions.append(Appointment.status.in_(["scheduled", "confirmed"]))
        elif status_filter == "past":
            conditions.append(or_(
                Appointment.start_time < now,
                Appointment.status.in_(["completed", "no_show"])
            ))
        elif status_filter == "cancelled":
            conditions.append(Appointment.status == "cancelled")
        
        stmt = select(Appointment).where(
            and_(*conditions)
        ).order_by(Appointment.start_time.desc())
        
        res = await session.execute(stmt)
        appointments = res.scalars().all()
        
        result = []
        for app in appointments:
            service = await srepo.get_by_id(app.service_id)
            result.append({
                "id": app.id,
                "service": service.name if service else "Услуга",
                "service_id": app.service_id,
                "service_price": service.price if service else 0,
                "start": app.start_time.isoformat(),
                "end": app.end_time.isoformat(),
                "status": app.status,
                "is_completed": app.is_completed,
                "payment_amount": app.payment_amount if app.payment_amount else 0,
                "client_comment": app.client_comment if app.client_comment else "",
            })
        
        return web.json_response({"appointments": result})


async def cancel_appointment_client(request: web.Request):
    """Allow client to cancel their appointment."""
    payload = await request.json()
    code = payload.get("code")
    telegram_id = payload.get("telegram_id")
    appointment_id = payload.get("appointment_id")
    
    if not all([code, telegram_id, appointment_id]):
        return web.json_response({"error": "missing fields"}, status=400)
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        crepo = ClientRepository(session)
        arepo = AppointmentRepository(session)
        
        master = await mrepo.get_by_referral_code(code)
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        client = await crepo.get_by_telegram_id(master.id, int(telegram_id))
        if not client:
            return web.json_response({"error": "client not found"}, status=404)
        
        appointment = await arepo.get_by_id(int(appointment_id))
        if not appointment or appointment.client_id != client.id:
            return web.json_response({"error": "appointment not found"}, status=404)
        
        if appointment.status not in [AppointmentStatus.SCHEDULED.value, AppointmentStatus.CONFIRMED.value]:
            return web.json_response({"error": "cannot cancel this appointment"}, status=400)
        
        appointment.status = AppointmentStatus.CANCELLED.value
        appointment.cancellation_reason = "Отменено клиентом"
        await arepo.update(appointment)
        
        # Cancel reminders
        try:
            reminder_repo = ReminderRepository(session)
            await reminder_repo.cancel_appointment_reminders(appointment.id)
        except Exception:
            pass
        
        await session.commit()
        
        # Notify master
        try:
            tz_name = master.timezone or "Europe/Moscow"
            tz = pytz_timezone(tz_name)
            local_start = appointment.start_time.replace(tzinfo=timezone.utc).astimezone(tz)
            when_str = local_start.strftime('%d.%m.%Y %H:%M')
            
            service = await ServiceRepository(session).get_by_id(appointment.service_id)
            service_name = service.name if service else "Услуга"
            
            text = (
                f"❌ Клиент отменил запись\n\n"
                f"Клиент: {client.name} ({client.phone})\n"
                f"Услуга: {service_name}\n"
                f"Время: {when_str} ({tz_name})"
            )
            await bot.send_message(master.telegram_id, text)
        except Exception as e:
            logger.error(f"Failed to notify master: {e}")
        
        return web.json_response({"ok": True})


async def reschedule_appointment_client(request: web.Request):
    """Allow client to reschedule their appointment."""
    payload = await request.json()
    code = payload.get("code")
    telegram_id = payload.get("telegram_id")
    appointment_id = payload.get("appointment_id")
    new_start_iso = payload.get("new_start")
    
    if not all([code, telegram_id, appointment_id, new_start_iso]):
        return web.json_response({"error": "missing fields"}, status=400)
    
    try:
        new_start = datetime.fromisoformat(new_start_iso)
    except Exception:
        return web.json_response({"error": "invalid date"}, status=400)
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        crepo = ClientRepository(session)
        arepo = AppointmentRepository(session)
        srepo = ServiceRepository(session)
        
        master = await mrepo.get_by_referral_code(code)
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        client = await crepo.get_by_telegram_id(master.id, int(telegram_id))
        if not client:
            return web.json_response({"error": "client not found"}, status=404)
        
        appointment = await arepo.get_by_id(int(appointment_id))
        if not appointment or appointment.client_id != client.id:
            return web.json_response({"error": "appointment not found"}, status=404)
        
        if appointment.status not in [AppointmentStatus.SCHEDULED.value, AppointmentStatus.CONFIRMED.value]:
            return web.json_response({"error": "cannot reschedule this appointment"}, status=400)
        
        service = await srepo.get_by_id(appointment.service_id)
        if not service:
            return web.json_response({"error": "service not found"}, status=404)
        
        # Normalize timezone
        try:
            tz = pytz_timezone(master.timezone or "Europe/Moscow")
            if new_start.tzinfo is None:
                local_dt = tz.localize(new_start)
                new_start = local_dt.astimezone(timezone.utc)
            else:
                new_start = new_start.astimezone(timezone.utc)
        except Exception:
            new_start = new_start.replace(tzinfo=timezone.utc)
        
        new_end = new_start + timedelta(minutes=service.duration_minutes)
        
        # Check conflict
        conflict = await arepo.check_time_conflict(master.id, new_start, new_end, exclude_appointment_id=appointment.id)
        if conflict:
            return web.json_response({"error": "time slot not available"}, status=409)
        
        old_start = appointment.start_time
        appointment.start_time = new_start
        appointment.end_time = new_end
        await arepo.update(appointment)
        
        # Recreate reminders
        try:
            await create_appointment_reminders(session, appointment, cancel_existing=True)
        except Exception:
            pass
        
        await session.commit()
        
        # Notify master
        try:
            tz_name = master.timezone or "Europe/Moscow"
            tz = pytz_timezone(tz_name)
            old_local = old_start.replace(tzinfo=timezone.utc).astimezone(tz)
            new_local = new_start.replace(tzinfo=timezone.utc).astimezone(tz)
            old_str = old_local.strftime('%d.%m.%Y %H:%M')
            new_str = new_local.strftime('%d.%m.%Y %H:%M')
            
            client_link = ""
            if client.telegram_username:
                safe_username = client.telegram_username.strip()
                if safe_username:
                    client_link = f" <a href=\"https://t.me/{safe_username}\">@{safe_username}</a>"
            elif client.telegram_id:
                client_link = f" <a href=\"tg://user?id={client.telegram_id}\">ID:{client.telegram_id}</a>"
            
            text = (
                f"🔄 Клиент перенес запись\n\n"
                f"Клиент: {client.name}{client_link}\n"
                f"Телефон: {client.phone}\n"
                f"Услуга: {service.name}\n"
                f"Было: {old_str}\n"
                f"Стало: {new_str} ({tz_name})"
            )
            await bot.send_message(master.telegram_id, text)
        except Exception as e:
            logger.error(f"Failed to notify master: {e}")
        
        return web.json_response({"ok": True})


# ========== Master API - Appointments ==========

async def get_master_appointments(request: web.Request):
    """Get appointments for a master on a specific date."""
    try:
        mid = request.query.get("mid")
        date_str = request.query.get("date")
        
        if not mid or mid == 'null' or mid == 'undefined':
            return web.json_response({"error": "mid required"}, status=400)
        
        try:
            mid_int = int(mid)
        except (ValueError, TypeError):
            return web.json_response({"error": "invalid mid"}, status=400)
        
        async with async_session_maker() as session:
            mrepo = MasterRepository(session)
            srepo = ServiceRepository(session)
            crepo = ClientRepository(session)
            
            master = await mrepo.get_by_telegram_id(mid_int)
            if not master:
                return web.json_response({"error": "master not found"}, status=404)
            
            tz = pytz_timezone(master.timezone or "Europe/Moscow")
            
            # Determine target date
            if date_str:
                try:
                    year, month, day = map(int, date_str.split('-'))
                    target_date = tz.localize(datetime(year, month, day, 0, 0))
                except Exception as e:
                    return web.json_response({"error": f"invalid date format: {str(e)}"}, status=400)
            else:
                now_local = datetime.now(timezone.utc).astimezone(tz)
                target_date = tz.localize(datetime(now_local.year, now_local.month, now_local.day, 0, 0))
            
            start_local = target_date
            end_local = start_local + timedelta(days=1)
            start_day = start_local.astimezone(timezone.utc).replace(tzinfo=None)
            end_day = end_local.astimezone(timezone.utc).replace(tzinfo=None)
            
            stmt = select(Appointment).where(
                Appointment.master_id == master.id,
                Appointment.start_time >= start_day,
                Appointment.start_time < end_day
            ).order_by(Appointment.start_time)
            
            res = await session.execute(stmt)
            apps = res.scalars().all()
            
            result = []
            for a in apps:
                service = await srepo.get_by_id(a.service_id)
                client = await crepo.get_by_id(a.client_id)
                start_local = a.start_time.replace(tzinfo=timezone.utc).astimezone(tz)
                end_local = a.end_time.replace(tzinfo=timezone.utc).astimezone(tz)
                is_past = a.start_time.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc)
                
                result.append({
                    "id": a.id,
                    "service": service.name if service else "",
                    "service_id": a.service_id,
                    "service_price": service.price if service else 0,
                    "client": {
                        "name": client.name,
                        "phone": client.phone,
                        "username": client.telegram_username,
                        "telegram_id": client.telegram_id
                    },
                    "start": start_local.isoformat(),
                    "end": end_local.isoformat(),
                    "status": a.status,
                    "is_completed": a.is_completed,
                    "is_past": is_past
                })
            
            return web.json_response({
                "referral_code": master.referral_code,
                "appointments": result,
                "work_schedule": master.work_schedule or {}
            })
    except Exception as e:
        logger.error(f"Error in get_master_appointments: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def get_master_schedule(request: web.Request):
    """Get master's schedule configuration."""
    mid = request.query.get("mid")
    if not mid:
        return web.json_response({"error": "mid required"}, status=400)
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        return web.json_response({
            "timezone": master.timezone,
            "city": master.city,
            "work_schedule": master.work_schedule or {}
        })


async def set_master_days_off(request: web.Request):
    """Update master's non-working weekdays and specific dates."""
    payload = await request.json()
    mid = payload.get("mid")
    days_off = payload.get("days_off") or []
    days_off_dates = payload.get("days_off_dates") or []
    
    if not isinstance(days_off, list) or not isinstance(days_off_dates, list):
        return web.json_response({"error": "invalid data format"}, status=400)
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        master = await mrepo.get_by_telegram_id(int(mid)) if mid else None
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        ws = dict(master.work_schedule or {})
        ws["days_off"] = days_off
        
        # Validate date strings
        valid_dates = []
        for ds in days_off_dates:
            try:
                datetime.strptime(ds, "%Y-%m-%d")
                valid_dates.append(ds)
            except Exception:
                pass
        ws["days_off_dates"] = valid_dates
        
        master.work_schedule = ws
        await mrepo.update(master)
        await session.commit()
        
        return web.json_response({"ok": True, "work_schedule": ws})


async def set_master_hours(request: web.Request):
    """Update master's working hours per weekday."""
    payload = await request.json()
    mid = payload.get("mid")
    hours = payload.get("hours") or {}
    
    if not isinstance(hours, dict):
        return web.json_response({"error": "hours must be object"}, status=400)
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        master = await mrepo.get_by_telegram_id(int(mid)) if mid else None
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        ws = master.work_schedule or {}
        
        def _valid_interval(iv):
            return isinstance(iv, list) and len(iv) == 2 and all(isinstance(x, str) for x in iv)
        
        for key in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            ivs = hours.get(key)
            if isinstance(ivs, list):
                clean = [iv for iv in ivs if _valid_interval(iv)]
                ws[key] = clean
        
        master.work_schedule = ws
        await mrepo.update(master)
        await session.commit()
        
        return web.json_response({"ok": True, "work_schedule": ws})


async def complete_appointment(request: web.Request):
    """Complete appointment and update client stats."""
    payload = await request.json()
    mid = payload.get("mid")
    appointment_id = payload.get("appointment_id")
    client_came = payload.get("client_came")
    payment_amount = payload.get("payment_amount")
    
    if not mid or not appointment_id or client_came is None:
        return web.json_response({"error": "mid, appointment_id, client_came required"}, status=400)
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        arepo = AppointmentRepository(session)
        crepo = ClientRepository(session)
        
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        appointment = await arepo.get_by_id(int(appointment_id))
        if not appointment or appointment.master_id != master.id:
            return web.json_response({"error": "appointment not found"}, status=404)
        
        if not client_came:
            appointment.status = AppointmentStatus.NO_SHOW.value
            appointment.is_completed = True
            await arepo.update(appointment)
            await session.commit()
            return web.json_response({"ok": True, "message": "Marked as no-show"})
        
        # Client came: update stats
        client = await crepo.get_by_id(appointment.client_id)
        if client:
            client.total_visits += 1
            if payment_amount is not None:
                client.total_spent += int(payment_amount)
            client.last_visit = appointment.start_time
            await crepo.update(client)
        
        appointment.status = AppointmentStatus.COMPLETED.value
        appointment.is_completed = True
        appointment.payment_amount = int(payment_amount) if payment_amount is not None else None
        await arepo.update(appointment)
        await session.commit()
        
        return web.json_response({"ok": True, "message": "Appointment completed"})


async def cancel_appointment_master(request: web.Request):
    """Cancel appointment by master."""
    payload = await request.json()
    mid = payload.get("mid")
    appointment_id = payload.get("appointment_id")
    reason = (payload.get("reason") or "").strip()
    
    if not (mid and appointment_id):
        return web.json_response({"error": "mid and appointment_id required"}, status=400)
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        arepo = AppointmentRepository(session)
        srepo = ServiceRepository(session)
        crepo = ClientRepository(session)
        
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        app = await arepo.get_by_id(appointment_id)
        if not app or app.master_id != master.id:
            return web.json_response({"error": "appointment not found"}, status=404)
        
        # Get service and client for notification
        service = await srepo.get_by_id(app.service_id)
        client = await crepo.get_by_id(app.client_id)
        
        app.status = AppointmentStatus.CANCELLED.value
        await arepo.update(app)
        
        # Cancel reminders
        try:
            reminder_repo = ReminderRepository(session)
            await reminder_repo.cancel_appointment_reminders(app.id)
        except Exception:
            pass
        
        await session.commit()
        
        # Notify client via reminder system
        if client and client.telegram_id:
            try:
                from database.models.reminder import ReminderType, ReminderChannel
                tz = pytz_timezone(master.timezone or "Europe/Moscow")
                start_local = app.start_time.replace(tzinfo=timezone.utc).astimezone(tz)
                
                # Create immediate reminder for notification
                reminder_repo = ReminderRepository(session)
                await reminder_repo.create(
                    appointment_id=app.id,
                    reminder_type=ReminderType.CANCELLED_BY_MASTER,
                    scheduled_time=datetime.now(timezone.utc),  # Send immediately
                    channel=ReminderChannel.TELEGRAM,
                    extra_data={"reason": reason} if reason else None
                )
                await session.commit()
                logger.info(f"Created cancellation reminder for client {client.telegram_id}")
            except Exception as e:
                logger.error(f"Failed to create cancellation reminder: {e}")
        
        return web.json_response({"ok": True})


async def reschedule_appointment_master(request: web.Request):
    """Reschedule appointment by master."""
    payload = await request.json()
    mid = payload.get("mid")
    appointment_id = payload.get("appointment_id")
    new_start_iso = payload.get("new_start")
    
    if not (mid and appointment_id and new_start_iso):
        return web.json_response({"error": "mid, appointment_id, new_start required"}, status=400)
    
    try:
        new_start = datetime.fromisoformat(new_start_iso)
    except Exception:
        return web.json_response({"error": "bad new_start"}, status=400)
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        arepo = AppointmentRepository(session)
        srepo = ServiceRepository(session)
        crepo = ClientRepository(session)
        
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        app = await arepo.get_by_id(appointment_id)
        if not app or app.master_id != master.id:
            return web.json_response({"error": "appointment not found"}, status=404)
        
        service = await srepo.get_by_id(app.service_id)
        client = await crepo.get_by_id(app.client_id)
        duration = service.duration_minutes if service else 60
        
        # Save old time for notification
        old_start = app.start_time
        
        # Normalize time
        try:
            tz = pytz_timezone(master.timezone or "Europe/Moscow")
            if new_start.tzinfo is None:
                local_dt = tz.localize(new_start)
                new_start_utc = local_dt.astimezone(timezone.utc)
            else:
                new_start_utc = new_start.astimezone(timezone.utc)
        except Exception:
            new_start_utc = new_start.replace(tzinfo=timezone.utc)
        
        new_end = new_start_utc + timedelta(minutes=duration)
        
        # Check conflict
        conflict = await arepo.check_time_conflict(master.id, new_start_utc, new_end, exclude_appointment_id=app.id)
        if conflict:
            return web.json_response({"error": "conflict"}, status=409)
        
        app.start_time = new_start_utc
        app.end_time = new_end
        app.status = AppointmentStatus.SCHEDULED.value
        await arepo.update(app)
        
        # Recreate reminders
        try:
            await create_appointment_reminders(session, app, cancel_existing=True)
        except Exception:
            pass
        
        await session.commit()
        
        # Notify client via reminder system
        if client and client.telegram_id:
            try:
                from database.models.reminder import ReminderType, ReminderChannel
                tz = pytz_timezone(master.timezone or "Europe/Moscow")
                old_local = old_start.replace(tzinfo=timezone.utc).astimezone(tz)
                new_local = new_start_utc.astimezone(tz)
                old_str = old_local.strftime("%d.%m.%Y в %H:%M")
                
                # Create immediate reminder for notification
                reminder_repo = ReminderRepository(session)
                await reminder_repo.create(
                    appointment_id=app.id,
                    reminder_type=ReminderType.RESCHEDULED,
                    scheduled_time=datetime.now(timezone.utc),  # Send immediately
                    channel=ReminderChannel.TELEGRAM,
                    extra_data={"old_time": old_str}
                )
                await session.commit()
                logger.info(f"Created reschedule reminder for client {client.telegram_id}")
            except Exception as e:
                logger.error(f"Failed to create reschedule reminder: {e}")
        
        return web.json_response({"ok": True})


# ========== Master API - Clients ==========

async def get_master_clients(request: web.Request):
    """Get list of all clients for a master."""
    try:
        mid = request.query.get("mid")
        if not mid or mid == 'null' or mid == 'undefined':
            return web.json_response({"error": "mid required"}, status=400)
        
        try:
            mid_int = int(mid)
        except (ValueError, TypeError):
            return web.json_response({"error": "invalid mid"}, status=400)
        
        async with async_session_maker() as session:
            mrepo = MasterRepository(session)
            master = await mrepo.get_by_telegram_id(mid_int)
            if not master:
                return web.json_response({"error": "master not found"}, status=404)
            
            res = await session.execute(
                select(Client).where(Client.master_id == master.id).order_by(Client.name)
            )
            clients = res.scalars().all()
            
            return web.json_response([
                {
                    "id": c.id,
                    "name": c.name,
                    "phone": c.phone,
                    "username": c.telegram_username,
                    "last_visit": c.last_visit.isoformat() if c.last_visit else None,
                    "total_visits": c.total_visits,
                    "total_spent": c.total_spent,
                }
                for c in clients
            ])
    except Exception as e:
        logger.error(f"Error in get_master_clients: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def get_client_history(request: web.Request):
    """Get appointment history for a specific client."""
    mid = request.query.get("mid")
    client_id = request.query.get("client_id")
    
    if not mid or not client_id:
        return web.json_response({"error": "mid and client_id required"}, status=400)
    
    async with async_session_maker() as session:
        from database.models.service import Service
        
        mrepo = MasterRepository(session)
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        # Verify client belongs to master
        client_res = await session.execute(
            select(Client).where(Client.id == int(client_id), Client.master_id == master.id)
        )
        client = client_res.scalar_one_or_none()
        if not client:
            return web.json_response({"error": "client not found"}, status=404)
        
        # Get appointments with services
        res = await session.execute(
            select(Appointment, Service)
            .join(Service, Appointment.service_id == Service.id)
            .where(Appointment.client_id == int(client_id))
            .order_by(Appointment.start_time.desc())
        )
        appointments = res.all()
        
        history = []
        for appt, service in appointments:
            history.append({
                "id": appt.id,
                "service_name": service.name,
                "start_time": appt.start_time.isoformat(),
                "status": appt.status,
                "is_completed": appt.is_completed,
                "payment_amount": appt.payment_amount,
                "service_price": service.price,
            })
        
        return web.json_response({
            "client": {
                "id": client.id,
                "name": client.name,
                "phone": client.phone,
                "username": client.telegram_username,
                "total_visits": client.total_visits,
                "total_spent": client.total_spent,
            },
            "appointments": history
        })


# ========== Master API - Services ==========

async def get_master_services(request: web.Request):
    """Get all services for a master."""
    try:
        mid = request.query.get("mid")
        if not mid or mid == 'null' or mid == 'undefined':
            return web.json_response({"error": "mid required"}, status=400)
        
        try:
            mid_int = int(mid)
        except (ValueError, TypeError):
            return web.json_response({"error": "invalid mid"}, status=400)
        
        async with async_session_maker() as session:
            mrepo = MasterRepository(session)
            srepo = ServiceRepository(session)
            
            master = await mrepo.get_by_telegram_id(mid_int)
            if not master:
                return web.json_response({"error": "master not found"}, status=404)
            
            services = await srepo.get_all_by_master(master.id, active_only=False)
            return web.json_response([
                {
                    "id": s.id,
                    "name": s.name,
                    "price": s.price,
                    "duration_minutes": s.duration_minutes,
                    "category": s.category,
                    "description": s.description,
                    "is_active": s.is_active
                }
                for s in services
            ])
    except Exception as e:
        logger.error(f"Error in get_master_services: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def save_master_service(request: web.Request):
    """Create or update a service."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)
    
    mid = data.get("mid")
    service_id = data.get("service_id")
    name = data.get("name", "").strip()
    price = data.get("price")
    duration = data.get("duration_minutes")
    category_raw = data.get("category", "")
    category = category_raw.strip() if category_raw else None
    description_raw = data.get("description", "")
    description = description_raw.strip() if description_raw else None
    is_active = data.get("is_active", True)
    
    if not mid or not name or price is None or duration is None:
        return web.json_response({"error": "mid, name, price, duration_minutes required"}, status=400)
    
    # Validate price and duration
    try:
        price = int(price)
        duration = int(duration)
        if price < 0:
            return web.json_response({"error": "price must be non-negative"}, status=400)
        if duration < 15 or duration > 480:
            return web.json_response({"error": "duration must be between 15 and 480 minutes"}, status=400)
    except (ValueError, TypeError):
        return web.json_response({"error": "invalid price or duration format"}, status=400)
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        srepo = ServiceRepository(session)
        
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        if service_id:
            # Update existing
            service = await srepo.get_by_id(int(service_id))
            if not service or service.master_id != master.id:
                return web.json_response({"error": "service not found"}, status=404)
            service.name = name
            service.price = price
            service.duration_minutes = duration
            service.category = category
            service.description = description
            service.is_active = is_active
        else:
            # Create new
            service = Service(
                master_id=master.id,
                name=name,
                price=price,
                duration_minutes=duration,
                category=category,
                description=description,
                is_active=is_active
            )
            session.add(service)
        
        await session.commit()
        return web.json_response({"ok": True, "service_id": service.id})


async def delete_master_service(request: web.Request):
    """Soft-delete a service."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)
    
    mid = data.get("mid")
    service_id = data.get("service_id")
    
    if not mid or not service_id:
        return web.json_response({"error": "mid, service_id required"}, status=400)
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        srepo = ServiceRepository(session)
        
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        service = await srepo.get_by_id(int(service_id))
        if not service or service.master_id != master.id:
            return web.json_response({"error": "service not found"}, status=404)
        
        service.is_active = False
        await session.commit()
        return web.json_response({"ok": True})


# ========== Master API - Financial ==========

async def get_financial_analytics(request: web.Request):
    """Get financial analytics for a master."""
    mid = request.query.get("mid")
    start_date_iso = request.query.get("start_date")
    end_date_iso = request.query.get("end_date")
    
    if not all([mid, start_date_iso, end_date_iso]):
        return web.json_response({"error": "mid, start_date, end_date required"}, status=400)
    
    try:
        start_date = datetime.fromisoformat(start_date_iso)
        end_date = datetime.fromisoformat(end_date_iso)
    except Exception:
        return web.json_response({"error": "invalid date format"}, status=400)
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        srepo = ServiceRepository(session)
        erepo = ExpenseRepository(session)
        
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        # Revenue calculation
        revenue_stmt = (
            select(func.sum(Appointment.payment_amount))
            .where(
                and_(
                    Appointment.master_id == master.id,
                    Appointment.is_completed == True,
                    Appointment.start_time >= start_date,
                    Appointment.start_time <= end_date
                )
            )
        )
        revenue_result = await session.execute(revenue_stmt)
        total_revenue = revenue_result.scalar() or 0
        
        # Count appointments
        count_stmt = (
            select(func.count(Appointment.id))
            .where(
                and_(
                    Appointment.master_id == master.id,
                    Appointment.is_completed == True,
                    Appointment.start_time >= start_date,
                    Appointment.start_time <= end_date
                )
            )
        )
        count_result = await session.execute(count_stmt)
        appointments_count = count_result.scalar() or 0
        
        # Revenue by service
        revenue_by_service_stmt = (
            select(
                Appointment.service_id,
                func.sum(Appointment.payment_amount).label('total'),
                func.count(Appointment.id).label('count')
            )
            .where(
                and_(
                    Appointment.master_id == master.id,
                    Appointment.is_completed == True,
                    Appointment.start_time >= start_date,
                    Appointment.start_time <= end_date
                )
            )
            .group_by(Appointment.service_id)
            .order_by(func.sum(Appointment.payment_amount).desc())
        )
        revenue_by_service_result = await session.execute(revenue_by_service_stmt)
        
        # FIX N+1: Prefetch all services at once instead of querying one by one
        rows = revenue_by_service_result.all()
        service_ids = [row.service_id for row in rows if row.service_id]
        
        # Single query to fetch all needed services
        services = await srepo.get_by_ids(service_ids)
        service_map = {s.id: s for s in services}
        
        # Build response using cached services
        revenue_by_service = []
        for row in rows:
            service = service_map.get(row.service_id) if row.service_id else None
            revenue_by_service.append({
                "service_name": service.name if service else "Unknown",
                "revenue": row.total or 0,
                "count": row.count
            })
        
        # Total expenses
        total_expenses = await erepo.get_total_by_period(
            master_id=master.id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Expenses by category
        expenses_by_category = await erepo.get_expenses_by_category(
            master_id=master.id,
            start_date=start_date,
            end_date=end_date
        )
        
        profit = total_revenue - total_expenses
        
        return web.json_response({
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "revenue": {
                "total": total_revenue,
                "appointments_count": appointments_count,
                "by_service": revenue_by_service
            },
            "expenses": {
                "total": total_expenses,
                "by_category": expenses_by_category
            },
            "profit": profit
        })


async def get_expenses(request: web.Request):
    """Get expenses for a master with filters."""
    mid = request.query.get("mid")
    start_date_iso = request.query.get("start_date")
    end_date_iso = request.query.get("end_date")
    category = request.query.get("category")
    
    if not mid:
        return web.json_response({"error": "mid required"}, status=400)
    
    start_date = None
    end_date = None
    
    try:
        if start_date_iso:
            start_date = datetime.fromisoformat(start_date_iso)
        if end_date_iso:
            end_date = datetime.fromisoformat(end_date_iso)
    except Exception:
        return web.json_response({"error": "invalid date format"}, status=400)
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        erepo = ExpenseRepository(session)
        
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        expenses = await erepo.get_by_master(
            master_id=master.id,
            start_date=start_date,
            end_date=end_date,
            category=category
        )
        
        return web.json_response({
            "expenses": [
                {
                    "id": e.id,
                    "category": e.category,
                    "amount": e.amount,
                    "expense_date": e.expense_date.isoformat(),
                    "description": e.description or ""
                }
                for e in expenses
            ]
        })


async def create_expense(request: web.Request):
    """Create a new expense."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)
    
    mid = data.get("mid")
    category = data.get("category")
    amount = data.get("amount")
    expense_date_iso = data.get("expense_date")
    description = data.get("description", "")
    
    if not all([mid, category, amount, expense_date_iso]):
        return web.json_response({"error": "mid, category, amount, expense_date required"}, status=400)
    
    try:
        amount = int(amount)
        expense_date = datetime.fromisoformat(expense_date_iso)
    except Exception:
        return web.json_response({"error": "invalid amount or date"}, status=400)
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        erepo = ExpenseRepository(session)
        
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        expense = await erepo.create(
            master_id=master.id,
            category=category,
            amount=amount,
            expense_date=expense_date,
            description=description
        )
        await session.commit()
        
        return web.json_response({
            "ok": True,
            "expense": {
                "id": expense.id,
                "category": expense.category,
                "amount": expense.amount,
                "expense_date": expense.expense_date.isoformat(),
                "description": expense.description
            }
        })


async def update_expense(request: web.Request):
    """Update an existing expense."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)
    
    mid = data.get("mid")
    expense_id = data.get("expense_id")
    
    if not all([mid, expense_id]):
        return web.json_response({"error": "mid and expense_id required"}, status=400)
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        erepo = ExpenseRepository(session)
        
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        expense = await erepo.get_by_id(int(expense_id))
        if not expense or expense.master_id != master.id:
            return web.json_response({"error": "expense not found"}, status=404)
        
        # Update fields if provided
        if "category" in data:
            expense.category = data["category"]
        if "amount" in data:
            try:
                expense.amount = int(data["amount"])
            except Exception:
                return web.json_response({"error": "invalid amount"}, status=400)
        if "expense_date" in data:
            try:
                expense.expense_date = datetime.fromisoformat(data["expense_date"])
            except Exception:
                return web.json_response({"error": "invalid date"}, status=400)
        if "description" in data:
            expense.description = data["description"]
        
        await erepo.update(expense)
        await session.commit()
        
        return web.json_response({"ok": True})


async def delete_expense(request: web.Request):
    """Delete an expense."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)
    
    mid = data.get("mid")
    expense_id = data.get("expense_id")
    
    if not all([mid, expense_id]):
        return web.json_response({"error": "mid and expense_id required"}, status=400)
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        erepo = ExpenseRepository(session)
        
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        expense = await erepo.get_by_id(int(expense_id))
        if not expense or expense.master_id != master.id:
            return web.json_response({"error": "expense not found"}, status=404)
        
        await erepo.delete(int(expense_id))
        await session.commit()
        
        return web.json_response({"ok": True})


# ========== Admin Analytics API ==========

async def get_retention_analytics(request: web.Request):
    """Get retention metrics (Day 1, Day 7, Day 30).
    
    Query params:
        - start_date (optional): ISO format date
        - end_date (optional): ISO format date
    
    Returns:
        {
            "day1": 70.5,
            "day7": 52.3,
            "day30": 38.1
        }
    """
    # TODO: Add admin authentication middleware
    # For now, anyone can access (will be protected by Telegram WebApp auth)
    
    start_date_str = request.query.get("start_date")
    end_date_str = request.query.get("end_date")
    
    start_date = None
    end_date = None
    
    try:
        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str)
        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str)
    except ValueError:
        return web.json_response({"error": "invalid date format"}, status=400)
    
    async with async_session_maker() as session:
        analytics_service = AnalyticsService(session)
        retention_data = await analytics_service.get_retention_report(
            start_date=start_date,
            end_date=end_date
        )
        
        return web.json_response(retention_data)


async def get_cohort_analytics(request: web.Request):
    """Get cohort analysis by registration week.
    
    Query params:
        - weeks (optional): Number of weeks to analyze (default: 8)
    
    Returns:
        [
            {
                "cohort_week": "2025-W48",
                "cohort_start": "2025-11-25T00:00:00",
                "registered": 15,
                "day0": 100.0,
                "day7": 80.0,
                "day14": 66.7,
                "day30": 53.3
            },
            ...
        ]
    """
    weeks_str = request.query.get("weeks", "8")
    
    try:
        weeks = int(weeks_str)
        if weeks < 1 or weeks > 52:
            weeks = 8
    except ValueError:
        weeks = 8
    
    async with async_session_maker() as session:
        analytics_service = AnalyticsService(session)
        cohort_data = await analytics_service.get_cohort_analysis(cohort_weeks=weeks)
        
        return web.json_response(cohort_data)


async def get_funnel_analytics(request: web.Request):
    """Get conversion funnel metrics.
    
    Returns:
        {
            "registered": {"count": 100, "rate": 100.0},
            "onboarded": {"count": 85, "rate": 85.0},
            "first_service": {"count": 72, "rate": 72.0},
            "first_booking": {"count": 58, "rate": 58.0},
            "paid": {"count": 45, "rate": 45.0}
        }
    """
    async with async_session_maker() as session:
        analytics_service = AnalyticsService(session)
        funnel_data = await analytics_service.get_funnel_conversion()
        
        return web.json_response(funnel_data)


async def get_growth_analytics(request: web.Request):
    """Get growth metrics (DAU, WAU, MAU, growth rate).
    
    Query params:
        - period (optional): 'day', 'week', or 'month' (default: 'month')
    
    Returns:
        {
            "dau": 234,
            "wau": 1523,
            "mau": 4891,
            "growth_rate": 12.5,
            "activation_rate": 68.5,
            "period": "month"
        }
    """
    period = request.query.get("period", "month")
    
    if period not in ['day', 'week', 'month']:
        period = 'month'
    
    async with async_session_maker() as session:
        analytics_service = AnalyticsService(session)
        growth_data = await analytics_service.get_growth_metrics(period=period)
        
        return web.json_response(growth_data)
