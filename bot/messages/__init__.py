"""
Messages package for centralized text management.

This package contains all user-facing messages organized by domain:
- common.py: Common messages used across the application
- appointments.py: Appointment-related messages
- subscriptions.py: Subscription and payment messages
- reminders.py: Reminder notification messages
- errors.py: Error messages
"""

from bot.messages.common import CommonMessages
from bot.messages.appointments import AppointmentMessages
from bot.messages.subscriptions import SubscriptionMessages
from bot.messages.reminders import ReminderMessages
from bot.messages.errors import ErrorMessages

__all__ = [
    'CommonMessages',
    'AppointmentMessages', 
    'SubscriptionMessages',
    'ReminderMessages',
    'ErrorMessages',
]
