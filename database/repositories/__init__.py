"""Database repositories package."""
from database.repositories.master import MasterRepository
from database.repositories.client import ClientRepository
from database.repositories.service import ServiceRepository
from database.repositories.appointment import AppointmentRepository

__all__ = [
    "MasterRepository",
    "ClientRepository",
    "ServiceRepository",
    "AppointmentRepository",
]
