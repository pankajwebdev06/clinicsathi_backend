from sqlalchemy import Column, String, Integer, DateTime, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum
from datetime import datetime

class Gender(str, enum.Enum):
    MALE = "M"
    FEMALE = "F"
    OTHER = "O"

class Patient(Base):
    __tablename__ = "patients"

    id = Column(String, primary_key=True)
    clinic_id = Column(String, nullable=False, index=True) 
    mobile_number = Column(String(10), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(Enum(Gender), nullable=False)
    
    # Consent & Legal Fields
    consent_given = Column(Boolean, nullable=False, default=False)
    consent_timestamp = Column(DateTime, nullable=True)
    consent_given_by = Column(String(20), default='receptionist')
    is_minor = Column(Boolean, nullable=True)
    guardian_name = Column(String(100), nullable=True)
    guardian_relationship = Column(String(50), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    queue_entries = relationship("QueueEntry", back_populates="patient")
    consultations = relationship("Consultation", back_populates="patient")
    prescriptions = relationship("Prescription", back_populates="patient")

    # Composite unique constraint
    __table_args__ = (
        UniqueConstraint('clinic_id', 'mobile_number'),
    )
