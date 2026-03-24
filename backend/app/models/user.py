from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    role: str = "worker"  # owner, admin, worker


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: str
    auth_id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: str
    updated_at: str


class LoginRequest(BaseModel):
    email: str
    password: str
