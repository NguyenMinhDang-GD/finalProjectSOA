import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field


RoleType = Literal["CUSTOMER", "STAFF", "ADMIN"]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)
    full_name: str = Field(min_length=2, max_length=150)
    phone: str = Field(min_length=8, max_length=20)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=100)


class CreateUserByAdminRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)
    full_name: str = Field(min_length=2, max_length=150)
    phone: str = Field(default="", max_length=20)
    role: RoleType = "STAFF"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    phone: str
    role: str
    is_active: bool
    created_at: datetime


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
