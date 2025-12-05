"""
WebApp URL utilities for building bot and web application links.
"""
from typing import Optional
from bot.config import settings
from database.models.master import Master


def build_webapp_link(master: Master, service_id: Optional[int] = None) -> str:
    """Build bot link that will show WebApp button for booking."""
    if not settings.bot_username:
        return ""
    # Use bot deep link with start parameter
    # When user opens this link, bot will show WebApp button
    params = master.referral_code
    if service_id:
        params += f"_{service_id}"  # Use underscore as separator
    return f"https://t.me/{settings.bot_username}?start={params}"


def build_webapp_url_direct(master: Master, service_id: Optional[int] = None) -> str:
    """Build direct WebApp URL for WebApp button."""
    if not settings.webapp_base_url:
        return ""
    base = str(settings.webapp_base_url).rstrip("/")
    if base.endswith("/webapp"):
        base_webapp = base
    else:
        base_webapp = base + "/webapp"
    params = f"?code={master.referral_code}"
    if service_id:
        params += f"&service={service_id}"
    return f"{base_webapp}/index.html{params}"


def build_client_appointments_url(master: Master) -> str:
    """Build WebApp URL for client to view their appointments."""
    if not settings.webapp_base_url:
        return ""
    base = str(settings.webapp_base_url).rstrip("/")
    if base.endswith("/webapp"):
        base_webapp = base
    else:
        base_webapp = base + "/webapp"
    return f"{base_webapp}/appointments.html?code={master.referral_code}"


def build_master_webapp_link(master: Master) -> str:
    """Build WebApp URL for master's personal dashboard."""
    if not settings.webapp_base_url:
        return ""
    base = str(settings.webapp_base_url).rstrip("/")
    # If WEBAPP_BASE_URL ends with /webapp, point to /webapp-master
    if base.endswith("/webapp"):
        base_master = base[:-7] + "/webapp-master"
    else:
        base_master = base + "/webapp-master"
    params = f"?mid={master.telegram_id}"
    return f"{base_master}/master.html{params}"
