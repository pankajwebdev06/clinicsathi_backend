from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi import Request
import uuid
import random
from datetime import datetime, timedelta
import time

# Simple in-memory rate limiter for OTP
otp_attempts = {}
def check_otp_rate_limit(ip: str):
    now = time.time()
    if ip in otp_attempts:
        otp_attempts[ip] = [t for t in otp_attempts[ip] if now - t < 300]  # 5 mins
    else:
        otp_attempts[ip] = []
    if len(otp_attempts[ip]) >= 5:  # Max 5 OTP requests per 5 mins
        return False
    otp_attempts[ip].append(now)
    return True

from app.core.database import get_db
from app.core.security import create_access_token
from app.core.deps import get_current_user, require_role
from app.features.auth.models import User, Clinic, UserRole
from app.features.auth.schemas import (
    ClinicCreate, ClinicResponse,
    UserRegister, UserResponse, TokenResponse,
    SendOTPRequest, VerifyOTPRequest, OTPResponse,
)

router = APIRouter()


def generate_otp() -> str:
    """Generate 6-digit OTP code."""
    return str(random.randint(100000, 999999))


# ═══════════════════════════════════════════════════════
#  CLINIC ENDPOINTS
# ═══════════════════════════════════════════════════════

@router.post("/clinics", response_model=ClinicResponse, status_code=status.HTTP_201_CREATED)
async def register_clinic(
    data: ClinicCreate,
    db: Session = Depends(get_db)
):
    """Register a new clinic. This is the first step in onboarding."""
    clinic = Clinic(
        id=str(uuid.uuid4()),
        name=data.name,
        doctor_name=data.doctor_name,
        specialization=data.specialization,
        city=data.city,
        address=data.address,
        phone=data.phone,
        created_at=datetime.utcnow(),
    )
    db.add(clinic)
    db.commit()
    db.refresh(clinic)
    return clinic


@router.get("/clinics/{clinic_id}", response_model=ClinicResponse)
async def get_clinic(
    clinic_id: str,
    db: Session = Depends(get_db)
):
    """Get clinic details by ID."""
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")
    return clinic


# ═══════════════════════════════════════════════════════
#  USER REGISTRATION & LOGIN
# ═══════════════════════════════════════════════════════

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    data: UserRegister,
    db: Session = Depends(get_db)
):
    """Register a new user (doctor / receptionist). No password needed - OTP based login."""
    # Check if mobile already exists
    existing = db.query(User).filter(User.mobile_number == data.mobile_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="Mobile number already registered")

    # Check if clinic exists
    clinic = db.query(Clinic).filter(Clinic.id == data.clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found. Register clinic first.")

    user = User(
        id=str(uuid.uuid4()),
        clinic_id=data.clinic_id,
        mobile_number=data.mobile_number,
        email=data.email,
        name=data.name,
        role=data.role,
        # No password - OTP based login
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/send-otp", response_model=OTPResponse)
async def send_otp(
    data: SendOTPRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Generate and send OTP to user's mobile number.
    
    In production: Send OTP via SMS/WhatsApp
    For demo: Returns OTP in response for testing
    """
    client_ip = request.client.host if request.client else "unknown"
    if not check_otp_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many OTP requests. Please wait 5 minutes.")
    
    # Check if user exists
    user = db.query(User).filter(User.mobile_number == data.mobile_number).first()
    if not user:
        raise HTTPException(status_code=404, detail="Mobile number not registered")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")
    
    # Generate OTP
    otp_code = generate_otp()
    otp_expires = datetime.utcnow() + timedelta(minutes=5)
    
    # Save OTP to user record
    user.otp_code = otp_code
    user.otp_expires_at = otp_expires
    db.commit()
    
    # Send OTP via SMS/WhatsApp/Email
    from app.services.otp_service import send_otp_to_user
    result = send_otp_to_user(
        phone=data.mobile_number,
        email=user.email,
        otp=otp_code,
        name=user.name
    )
    
    # If no service configured, return OTP in response for demo
    demo_otp = otp_code if not any([result["sms"], result["whatsapp"], result["email"]]) else None
    
    channels_sent = []
    if result["sms"]: channels_sent.append("SMS")
    if result["whatsapp"]: channels_sent.append("WhatsApp")
    if result["email"]: channels_sent.append("Email")
    
    message = f"OTP sent to {data.mobile_number}"
    if channels_sent:
        message += f" via {', '.join(channels_sent)}"
    else:
        message = f"OTP ready (no messaging service configured)"
    
    return OTPResponse(
        message=message,
        expires_in_seconds=300,
        demo_otp=demo_otp  # Only shown if no services configured
    )


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp(
    data: VerifyOTPRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Verify OTP and login. Returns JWT token on success."""
    client_ip = request.client.host if request.client else "unknown"
    if not check_otp_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait 5 minutes.")
    
    user = db.query(User).filter(User.mobile_number == data.mobile_number).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mobile number not found",
        )
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")
    
    # Check OTP
    if not user.otp_code or not user.otp_expires_at:
        raise HTTPException(status_code=400, detail="No OTP requested. Please request OTP first.")
    
    # Check if OTP expired
    if datetime.utcnow() > user.otp_expires_at:
        raise HTTPException(status_code=400, detail="OTP expired. Please request new OTP.")
    
    # Verify OTP code
    if user.otp_code != data.otp_code:
        raise HTTPException(status_code=401, detail="Invalid OTP code")
    
    # Clear OTP after successful verification
    user.otp_code = None
    user.otp_expires_at = None
    db.commit()
    
    # Create JWT with user info
    token = create_access_token(data={
        "sub": user.id,
        "clinic_id": user.clinic_id,
        "role": user.role,
    })
    
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


# Legacy endpoint - redirect to OTP flow
@router.post("/login", response_model=OTPResponse)
async def login_legacy(
    data: SendOTPRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Legacy login endpoint - now sends OTP instead.
    
    This maintains backward compatibility while migrating to OTP flow.
    """
    return await send_otp(data, request, db)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Get the current logged-in user's info. Requires Bearer token."""
    return current_user


@router.get("/staff", response_model=list[UserResponse])
async def get_clinic_staff(
    clinic_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("doctor")),
):
    """Get all receptionist staff for a clinic. Doctor only."""
    staff = db.query(User).filter(
        User.clinic_id == clinic_id,
        User.role == UserRole.RECEPTIONIST,
    ).all()
    return staff

