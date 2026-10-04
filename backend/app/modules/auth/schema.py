import re
from typing import Self
from pydantic import BaseModel, Field, model_validator


class LoginRequest(BaseModel):
    phone: str | None = Field(default=None, description="10-digit mobile phone number")
    pin: str | None = Field(default=None, description="4-6 digit numeric PIN")
    email: str | None = Field(default=None, description="Email address for platform admin")
    password: str | None = Field(default=None, description="Account password")

    @model_validator(mode="after")
    def validate_credentials_presence(self) -> Self:
        has_phone_pin = bool(self.phone and self.pin)
        has_email_password = bool(self.email and self.password)

        if not (has_phone_pin or has_email_password):
            raise ValueError("Must provide either (phone and pin) or (email and password).")

        if self.phone:
            cleaned_phone = re.sub(r"\D", "", self.phone)
            if len(cleaned_phone) != 10:
                raise ValueError("Phone number must be exactly 10 digits.")
            self.phone = cleaned_phone

        if self.pin:
            if not self.pin.isdigit() or not (4 <= len(self.pin) <= 6):
                raise ValueError("PIN must be 4 to 6 numeric digits.")

        if self.email:
            self.email = self.email.strip().lower()

        return self


class RefreshRequest(BaseModel):
    refresh_token: str | None = Field(default=None, description="Refresh token string")


class UserSummary(BaseModel):
    id: str
    name: str
    restaurant_id: str | None
    roles: list[str]


class TokenResponseData(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_seconds: int = 900
    user: UserSummary
