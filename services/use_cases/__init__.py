"""
Use Cases package for business logic encapsulation.

This package contains use case classes that encapsulate business logic
and orchestrate interactions between repositories and services.
"""

from services.use_cases.appointments import (
    GetAppointmentsUseCase,
    CreateAppointmentUseCase,
    CompleteAppointmentUseCase,
    CancelAppointmentUseCase,
)

__all__ = [
    'GetAppointmentsUseCase',
    'CreateAppointmentUseCase',
    'CompleteAppointmentUseCase',
    'CancelAppointmentUseCase',
]
