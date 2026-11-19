import re
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator


USERNAME_REGEX = re.compile(r"^[a-z0-9_]{3,20}$")


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str = Field(min_length=6)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        clean = v.strip().lower()
        if not USERNAME_REGEX.match(clean):
            raise ValueError(
                "Username must be 3-20 characters long and contain only lowercase letters, numbers, and underscores."
            )
        return clean


class LoginRequest(BaseModel):
    login: str  # Email or username
    password: str

    @field_validator("login", mode="before")
    @classmethod
    def normalize_login(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class ChangeUsernameRequest(BaseModel):
    new_username: str

    @field_validator("new_username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        clean = v.strip().lower()
        if not USERNAME_REGEX.match(clean):
            raise ValueError(
                "Username must be 3-20 characters long and contain only lowercase letters, numbers, and underscores."
            )
        return clean


class DeleteAccountRequest(BaseModel):
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    has_wallet: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class SessionResponse(BaseModel):
    id: int
    user_agent: str | None
    ip: str | None
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    is_current: bool = False

    class Config:
        from_attributes = True
