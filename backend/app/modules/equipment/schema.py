import uuid
from datetime import datetime
from decimal import Decimal
from typing import Self
from pydantic import BaseModel, Field, field_validator, model_validator

VALID_EQUIPMENT_STATUSES = {"OPERATIONAL", "MAINTENANCE", "DECOMMISSIONED"}


class EquipmentCreate(BaseModel):
    restaurant_id: uuid.UUID | None = Field(default=None, description="Restaurant outlet ID (defaults to TenantContext)")
    name: str = Field(min_length=2, max_length=200, description="Equipment display name (e.g., Walk-In Chiller #1)")
    equipment_type: str = Field(min_length=2, max_length=80, description="Equipment type classification (e.g., CHILLER, FREEZER, DISHWASHER)")
    location: str | None = Field(default=None, max_length=120, description="Kitchen location label (e.g., Prep Area Line 2)")
    serial_number: str | None = Field(default=None, max_length=100, description="Equipment serial or asset tag number")
    min_temp: Decimal | float | None = Field(default=None, description="Minimum safe operational temperature limit")
    max_temp: Decimal | float | None = Field(default=None, description="Maximum safe operational temperature limit")
    status: str = Field(default="OPERATIONAL", description="Operational status: OPERATIONAL, MAINTENANCE, DECOMMISSIONED")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        upper_v = v.strip().upper()
        if upper_v not in VALID_EQUIPMENT_STATUSES:
            raise ValueError(f"Status must be one of {sorted(list(VALID_EQUIPMENT_STATUSES))}.")
        return upper_v

    @field_validator("equipment_type")
    @classmethod
    def validate_equipment_type(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if not cleaned:
            raise ValueError("equipment_type cannot be empty.")
        return cleaned

    @model_validator(mode="after")
    def validate_temperature_range(self) -> Self:
        if self.min_temp is not None and self.max_temp is not None:
            if float(self.min_temp) > float(self.max_temp):
                raise ValueError("min_temp cannot be greater than max_temp.")
        return self


class EquipmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    equipment_type: str | None = Field(default=None, min_length=2, max_length=80)
    location: str | None = Field(default=None, max_length=120)
    serial_number: str | None = Field(default=None, max_length=100)
    min_temp: Decimal | float | None = Field(default=None)
    max_temp: Decimal | float | None = Field(default=None)
    status: str | None = Field(default=None)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is None:
            return v
        upper_v = v.strip().upper()
        if upper_v not in VALID_EQUIPMENT_STATUSES:
            raise ValueError(f"Status must be one of {sorted(list(VALID_EQUIPMENT_STATUSES))}.")
        return upper_v

    @field_validator("equipment_type")
    @classmethod
    def validate_equipment_type(cls, v: str | None) -> str | None:
        if v is None:
            return v
        cleaned = v.strip().upper()
        if not cleaned:
            raise ValueError("equipment_type cannot be empty.")
        return cleaned

    @model_validator(mode="after")
    def validate_temperature_range(self) -> Self:
        if self.min_temp is not None and self.max_temp is not None:
            if float(self.min_temp) > float(self.max_temp):
                raise ValueError("min_temp cannot be greater than max_temp.")
        return self


class EquipmentResponse(BaseModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID
    name: str
    equipment_type: str
    location: str | None
    serial_number: str | None
    min_temp: float | None
    max_temp: float | None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
