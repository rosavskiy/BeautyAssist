"""Keyboards package."""
from bot.keyboards.master import (
    get_main_menu_keyboard,
    get_services_keyboard,
    get_service_actions_keyboard,
    get_appointments_keyboard,
    get_appointment_actions_keyboard,
    get_back_keyboard,
    get_confirm_keyboard,
    get_weekdays_keyboard,
)
from bot.keyboards.client import (
    get_services_selection_keyboard,
    get_dates_keyboard,
    get_time_slots_keyboard,
    get_booking_confirm_keyboard,
    get_appointment_client_actions_keyboard,
)

__all__ = [
    "get_main_menu_keyboard",
    "get_services_keyboard",
    "get_service_actions_keyboard",
    "get_appointments_keyboard",
    "get_appointment_actions_keyboard",
    "get_back_keyboard",
    "get_confirm_keyboard",
    "get_weekdays_keyboard",
    "get_services_selection_keyboard",
    "get_dates_keyboard",
    "get_time_slots_keyboard",
    "get_booking_confirm_keyboard",
    "get_appointment_client_actions_keyboard",
]
