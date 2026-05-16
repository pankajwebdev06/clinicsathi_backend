from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.features.auth.models import User
from app.features.patients.models import Patient
from app.features.patients.schemas import PatientCreate, PatientResponse, PatientUpdate
from datetime import datetime

router = APIRouter()


@router.post("/", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(
    patient_data: PatientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("doctor", "receptionist")),
):
    """Create a new patient. Accessible by doctor or receptionist."""
    # Check if patient exists
    existing = db.query(Patient).filter(
        Patient.clinic_id == patient_data.clinic_id,
        Patient.mobile_number == patient_data.mobile_number
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Patient already exists for this clinic")

    if not patient_data.consent_given:
        raise HTTPException(status_code=400, detail="Patient consent is required before registration.")

    # Create new patient
    new_patient_dict = patient_data.model_dump()
    new_patient_dict["is_minor"] = new_patient_dict["age"] < 18
    new_patient_dict["consent_timestamp"] = datetime.utcnow()
    
    new_patient = Patient(
        id=str(uuid.uuid4()),
        **new_patient_dict
    )
    db.add(new_patient)
    db.commit()
    db.refresh(new_patient)
    return new_patient


@router.get("/", response_model=List[PatientResponse])
async def get_patients(
    clinic_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("doctor", "receptionist")),
):
    """List all patients for a clinic. Accessible by doctor or receptionist."""
    patients = db.query(Patient).filter(Patient.clinic_id == clinic_id).offset(skip).limit(limit).all()
    return patients

@router.patch("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: str,
    patient_data: PatientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("doctor", "receptionist")),
):
    """Update patient details."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    update_data = patient_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(patient, key, value)

    patient.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(patient)
    return patient


@router.get("/export", response_model=dict)
async def export_patients(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("doctor")),
):
    """Export all patient records for a clinic. Accessible by doctor only."""
    patients = db.query(Patient).filter(Patient.clinic_id == current_user.clinic_id).all()
    
    # Exclude internal ORM state
    patient_list = []
    for p in patients:
        p_dict = {
            "id": p.id,
            "mobile_number": p.mobile_number,
            "name": p.name,
            "age": p.age,
            "gender": p.gender.value,
            "consent_given": p.consent_given,
            "consent_timestamp": p.consent_timestamp.isoformat() if p.consent_timestamp else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        patient_list.append(p_dict)
        
    return {
        "exportedAt": datetime.utcnow().isoformat(),
        "totalRecords": len(patient_list),
        "data": patient_list
    }
