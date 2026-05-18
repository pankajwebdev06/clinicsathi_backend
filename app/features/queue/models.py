from sqlalchemy import Column, String, DateTime, Enum, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum
from datetime import datetime


class QueueStatus(str, enum.Enum):
    WAITING = "waiting"
    IN_CONSULTATION = "in_consultation"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class QueueEntry(Base):
    __tablename__ = "queue_entries"

    id = Column(String, primary_key=True)
    clinic_id = Column(String, nullable=False, index=True)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    token_number = Column(String, nullable=False)
    status = Column(Enum(QueueStatus), default=QueueStatus.WAITING, nullable=False)
    priority = Column(Integer, default=0)
    symptoms = Column(String, nullable=True)
    bp = Column(String, nullable=True)
    weight = Column(String, nullable=True)
    temperature = Column(String, nullable=True)
    pulse = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    patient = relationship("Patient", back_populates="queue_entries")
