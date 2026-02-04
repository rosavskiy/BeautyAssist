"""
Data Transfer Objects (DTOs) for data validation.

This package contains Pydantic models for validating input data.
"""

from core.dto.appointments import (
    CreateAppointmentDTO,
    UpdateAppointmentDTO,
    CompleteAppointmentDTO,
)
from core.dto.clients import (
    CreateClientDTO,
    UpdateClientDTO,
)
from core.dto.services import (
    CreateServiceDTO,
    UpdateServiceDTO,
)

__all__ = [
    'CreateAppointmentDTO',
    'UpdateAppointmentDTO',
    'CompleteAppointmentDTO',
    'CreateClientDTO',
    'UpdateClientDTO',
    'CreateServiceDTO',
    'UpdateServiceDTO',
]
