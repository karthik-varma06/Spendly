from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Full name must be at least 2 characters long")
        return v


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: UUID
    full_name: str
    email: EmailStr
    currency: str = "INR"
    timezone: str = "Asia/Kolkata"
    profile_image: str | None = None
    is_verified: bool = False
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class AuthMeResponse(BaseModel):
    authenticated: bool
    user: UserOut | None = None