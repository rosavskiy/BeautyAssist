"""Service DTOs for data validation."""
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class CreateServiceDTO(BaseModel):
    """DTO for creating a new service."""
    
    master_id: int = Field(..., description="Master ID who offers this service")
    name: str = Field(..., min_length=1, max_length=100, description="Service name")
    duration_minutes: int = Field(..., ge=5, le=480, description="Duration in minutes (5-480)")
    price: int = Field(..., ge=0, le=1000000, description="Price in rubles (0-1000000)")
    category: Optional[str] = Field(None, max_length=50, description="Service category")
    description: Optional[str] = Field(None, max_length=500, description="Service description")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Clean and validate service name."""
        return v.strip()
    
    @field_validator('duration_minutes')
    @classmethod
    def validate_duration(cls, v: int) -> int:
        """Validate duration is reasonable."""
        if v % 5 != 0:
            # Round to nearest 5 minutes
            v = round(v / 5) * 5
        return max(5, min(v, 480))


class UpdateServiceDTO(BaseModel):
    """DTO for updating a service."""
    
    service_id: int = Field(..., description="Service ID to update")
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="New name")
    duration_minutes: Optional[int] = Field(None, ge=5, le=480, description="New duration")
    price: Optional[int] = Field(None, ge=0, le=1000000, description="New price")
    category: Optional[str] = Field(None, max_length=50, description="New category")
    description: Optional[str] = Field(None, max_length=500, description="New description")
    is_active: Optional[bool] = Field(None, description="Active status")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Clean service name if provided."""
        return v.strip() if v else v
