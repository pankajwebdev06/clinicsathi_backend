from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


# ── Clinic ──────────────────────────────────────────────
class ClinicCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    doctor_name: str = Field(..., min_length=2, max_length=100)
    specialization: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    mci_number: Optional[str] = None
    gstin: Optional[str] = None
    phone: Optional[str] = None


class ClinicResponse(BaseModel):
    id: str
    name: str
    doctor_name: str
    specialization: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    mci_number: Optional[str] = None
    gstin: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── User / Auth ─────────────────────────────────────────
class UserRegister(BaseModel):
    mobile_number: str = Field(..., min_length=10, max_length=10)
    name: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=6)
    role: str = Field("doctor", description="doctor | receptionist | admin")
    clinic_id: str


class UserLogin(BaseModel):
    mobile_number: str = Field(..., min_length=10, max_length=10)
    password: str = Field(..., min_length=6)


class UserResponse(BaseModel):
    id: str
    clinic_id: str
    mobile_number: str
    name: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
