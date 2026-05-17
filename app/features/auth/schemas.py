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


class ClinicUpdate(BaseModel):
    name: Optional[str] = None
    doctor_name: Optional[str] = None
    specialization: Optional[str] = None
    degree: Optional[str] = None
    experience: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    mci_number: Optional[str] = None
    gstin: Optional[str] = None
    phone: Optional[str] = None
    doctor_photo: Optional[str] = None
    clinic_photo: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    about_doctor: Optional[str] = None
    services: Optional[str] = None
    consultation_fee: Optional[str] = None
    # Prescription template selection (preset id 't1'..'t5' or 'custom')
    selected_template: Optional[str] = None
    # JSON-serialised TemplateConfig (only used when selected_template == 'custom')
    template_config: Optional[str] = None


class ClinicResponse(BaseModel):
    id: str
    name: str
    slug: str
    doctor_name: str
    specialization: Optional[str] = None
    degree: Optional[str] = None
    experience: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    mci_number: Optional[str] = None
    gstin: Optional[str] = None
    phone: Optional[str] = None
    doctor_photo: Optional[str] = None
    clinic_photo: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    about_doctor: Optional[str] = None
    services: Optional[str] = None
    consultation_fee: Optional[str] = None
    selected_template: Optional[str] = 't1'
    template_config: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── User / Auth ─────────────────────────────────────────
class UserRegister(BaseModel):
    mobile_number: str = Field(..., min_length=10, max_length=10)
    email: Optional[str] = Field(None, description="Optional email for notifications")
    name: str = Field(..., min_length=2, max_length=100)
    role: str = Field("doctor", description="doctor | receptionist | admin")
    clinic_id: str


class SendOTPRequest(BaseModel):
    """Request OTP for login - sent to mobile/email"""
    mobile_number: str = Field(..., min_length=10, max_length=10)


class VerifyOTPRequest(BaseModel):
    """Verify OTP and login"""
    mobile_number: str = Field(..., min_length=10, max_length=10)
    otp_code: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")


class UserResponse(BaseModel):
    id: str
    clinic_id: str
    mobile_number: str
    email: Optional[str] = None
    name: str
    role: str
    preferred_language: Optional[str] = 'en'
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserPreferencesUpdate(BaseModel):
    preferred_language: Optional[str] = Field(None, min_length=2, max_length=5)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class OTPResponse(BaseModel):
    """Response after requesting OTP"""
    message: str
    expires_in_seconds: int = 300  # 5 minutes default
    # In production, don't return OTP in response - send via SMS/Email
    # This is for demo/testing purposes
    demo_otp: Optional[str] = None  # Only for development!
