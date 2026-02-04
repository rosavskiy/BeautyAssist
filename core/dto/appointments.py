"""Appointment DTOs for data validation."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class CreateAppointmentDTO(BaseModel):
    """DTO for creating a new appointment."""
    
    master_id: int = Field(..., description="Master ID")
    client_id: int = Field(..., description="Client ID")
    service_id: int = Field(..., description="Service ID")
    start_time: datetime = Field(..., description="Appointment start time (UTC)")
    notes: Optional[str] = Field(None, max_length=500, description="Optional notes")
    
    @field_validator('start_time')
    @classmethod
    def validate_start_time(cls, v: datetime) -> datetime:
        """Ensure start_time is not in the past."""
        if v < datetime.utcnow():
            raise ValueError("Нельзя создать запись в прошлом")
        return v


class UpdateAppointmentDTO(BaseModel):
    """DTO for updating an appointment."""
    
    appointment_id: int = Field(..., description="Appointment ID")
    start_time: Optional[datetime] = Field(None, description="New start time")
    service_id: Optional[int] = Field(None, description="New service ID")
    notes: Optional[str] = Field(None, max_length=500, description="Updated notes")
    
    @field_validator('start_time')
    @classmethod
    def validate_start_time(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure start_time is not in the past if provided."""
        if v is not None and v < datetime.utcnow():
            raise ValueError("Нельзя перенести запись в прошлое")
        return v


class CompleteAppointmentDTO(BaseModel):
    """DTO for completing an appointment."""
    
    appointment_id: int = Field(..., description="Appointment ID")
    client_showed: bool = Field(..., description="Whether client showed up")
    payment_amount: Optional[int] = Field(None, ge=0, description="Payment amount in rubles")
    notes: Optional[str] = Field(None, max_length=500, description="Completion notes")


class CancelAppointmentDTO(BaseModel):
    """DTO for cancelling an appointment."""
    
    appointment_id: int = Field(..., description="Appointment ID")
    reason: Optional[str] = Field(None, max_length=500, description="Cancellation reason")
    cancelled_by: str = Field(..., description="Who cancelled: 'master' or 'client'")
    
    @field_validator('cancelled_by')
    @classmethod
    def validate_cancelled_by(cls, v: str) -> str:
        """Ensure valid cancelled_by value."""
        if v not in ('master', 'client'):
            raise ValueError("cancelled_by must be 'master' or 'client'")
        return v
