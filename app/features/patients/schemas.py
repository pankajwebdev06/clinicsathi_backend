from pydantic import BaseModel, constr
from datetime import datetime
from typing import Optional
from app.features.patients.models import Gender

class PatientBase(BaseModel):
    clinic_id: str
    mobile_number: str
    name: str
    age: int
    gender: Gender

class PatientCreate(PatientBase):
    consent_given: bool

class PatientResponse(PatientBase):
    id: str
    consent_given: bool
    consent_timestamp: Optional[datetime] = None
    consent_given_by: Optional[str] = None
    is_minor: Optional[bool] = None
    guardian_name: Optional[str] = None
    guardian_relationship: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
