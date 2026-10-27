"""
Auth Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional
from .timestamps import TimestampString


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Full name of student")
    email: str = Field(..., min_length=5, max_length=255, description="Valid student email address")
    password: str = Field(..., min_length=6, max_length=128, description="Password (at least 6 characters)")


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255, description="Registered email address")
    password: str = Field(..., min_length=1, description="Account password")


class UserProfileResponse(BaseModel):
    id: str
    name: str
    email: str
    created_at: Optional[TimestampString] = None


class AuthResponse(BaseModel):
    token: str
    token_type: str = "Bearer"
    user: UserProfileResponse
    demo_notice: str = "Demo authentication active. Token valid for local session."
