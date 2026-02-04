"""Client DTOs for data validation."""
import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class CreateClientDTO(BaseModel):
    """DTO for creating a new client."""
    
    master_id: int = Field(..., description="Master ID who owns this client")
    name: str = Field(..., min_length=1, max_length=100, description="Client name")
    phone: str = Field(..., description="Client phone number")
    telegram_id: Optional[int] = Field(None, description="Telegram user ID")
    telegram_username: Optional[str] = Field(None, max_length=32, description="Telegram username")
    source: Optional[str] = Field(None, max_length=50, description="How client found the master")
    notes: Optional[str] = Field(None, max_length=1000, description="Notes about client")
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate and normalize phone number."""
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', v)
        
        # Check length (Russian numbers should be 11 digits)
        if len(digits) < 10 or len(digits) > 15:
            raise ValueError("Неверный формат телефона")
        
        # Normalize to +7 format for Russian numbers
        if len(digits) == 11 and digits.startswith('8'):
            digits = '7' + digits[1:]
        elif len(digits) == 10:
            digits = '7' + digits
        
        return '+' + digits
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Clean and validate name."""
        return v.strip()


class UpdateClientDTO(BaseModel):
    """DTO for updating a client."""
    
    client_id: int = Field(..., description="Client ID to update")
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="New name")
    phone: Optional[str] = Field(None, description="New phone number")
    telegram_id: Optional[int] = Field(None, description="Updated Telegram ID")
    telegram_username: Optional[str] = Field(None, max_length=32, description="Updated Telegram username")
    notes: Optional[str] = Field(None, max_length=1000, description="Updated notes")
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize phone number if provided."""
        if v is None:
            return v
        
        digits = re.sub(r'\D', '', v)
        
        if len(digits) < 10 or len(digits) > 15:
            raise ValueError("Неверный формат телефона")
        
        if len(digits) == 11 and digits.startswith('8'):
            digits = '7' + digits[1:]
        elif len(digits) == 10:
            digits = '7' + digits
        
        return '+' + digits
