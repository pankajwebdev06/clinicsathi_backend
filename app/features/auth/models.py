from sqlalchemy import Column, String, DateTime, Enum, Boolean
from app.core.database import Base
import enum
from datetime import datetime


class UserRole(str, enum.Enum):
    DOCTOR = "doctor"
    RECEPTIONIST = "receptionist"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    clinic_id = Column(String, nullable=False, index=True)
    mobile_number = Column(String(10), nullable=False, unique=True, index=True)
    email = Column(String(100), nullable=True)  # Optional email for notifications
    name = Column(String(100), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    # OTP fields - no password needed
    otp_code = Column(String(6), nullable=True)  # 6-digit OTP
    otp_expires_at = Column(DateTime, nullable=True)  # OTP expiry time
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Clinic(Base):
    __tablename__ = "clinics"

    id = Column(String, primary_key=True)
    name = Column(String(200), nullable=False)
    doctor_name = Column(String(100), nullable=False)
    specialization = Column(String(100))
    city = Column(String(100))
    address = Column(String(500))
    mci_number = Column(String(20))
    gstin = Column(String(15))
    phone = Column(String(15))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
