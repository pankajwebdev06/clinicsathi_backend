from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid
from datetime import datetime

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.core.deps import get_current_user, require_role
from app.features.auth.models import User, Clinic, UserRole
from app.features.auth.schemas import (
    ClinicCreate, ClinicResponse,
    UserRegister, UserLogin, UserResponse, TokenResponse,
)

router = APIRouter()


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
    """Register a new user (doctor / receptionist)."""
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
        name=data.name,
        role=data.role,
        hashed_password=hash_password(data.password),
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    data: UserLogin,
    db: Session = Depends(get_db)
):
    """Login with mobile number and password. Returns JWT token."""
    user = db.query(User).filter(User.mobile_number == data.mobile_number).first()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid mobile number or password",
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

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

