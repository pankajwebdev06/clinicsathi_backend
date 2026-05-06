from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session
from typing import List
import uuid
import json

from app.core.database import get_db
from app.core.deps import require_role
from app.features.auth.models import User
from app.features.consultations.models import Consultation
from app.features.consultations.schemas import ConsultationCreate, ConsultationResponse, ConsultationUpdate
from app.utils.image_processor import compress_image
from app.services.storage_service import storage_service

router = APIRouter()


@router.post("/", response_model=ConsultationResponse, status_code=status.HTTP_201_CREATED)
async def create_consultation(
    data: ConsultationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("doctor")),
):
    """Create a new consultation with doctor notes. Doctor only."""
    consultation = Consultation(
        id=str(uuid.uuid4()),
        **data.model_dump()
    )
    db.add(consultation)
    db.commit()
    db.refresh(consultation)
    return consultation


@router.get("/patient/{patient_id}", response_model=List[ConsultationResponse])
async def get_patient_history(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("doctor", "receptionist")),
):
    """Get all previous consultations for a patient. Doctor or receptionist."""
    history = db.query(Consultation).filter(
        Consultation.patient_id == patient_id
    ).order_by(Consultation.created_at.desc()).all()
    return history


@router.get("/{consultation_id}", response_model=ConsultationResponse)
async def get_consultation(
    consultation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("doctor")),
):
    """Get specific consultation details. Doctor only."""
    consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    return consultation


@router.patch("/{consultation_id}", response_model=ConsultationResponse)
async def update_notes(
    consultation_id: str,
    data: ConsultationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("doctor")),
):
    """Update doctor's notes in a consultation. Doctor only."""
    consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(consultation, key, value)

    db.commit()
    db.refresh(consultation)
    return consultation


@router.post("/{consultation_id}/upload-prescription", response_model=ConsultationResponse)
async def upload_prescription(
    consultation_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("receptionist")),
):
    """Upload a handwritten prescription photo. Receptionist only."""
    consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")

    # 1. Read and compress image
    content = await file.read()
    compressed_content = compress_image(content)

    # 2. Upload to Cloudinary
    url = await storage_service.upload_file(
        file_content=compressed_content,
        filename=f"{consultation_id}_prescription.webp",
        folder="prescriptions"
    )

    if not url:
        raise HTTPException(status_code=500, detail="Failed to upload image to storage")

    # 3. Update database
    consultation.handwritten_prescription_url = url
    db.commit()
    db.refresh(consultation)
    return consultation


@router.post("/{consultation_id}/upload-report", response_model=ConsultationResponse)
async def upload_report(
    consultation_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("receptionist")),
):
    """Upload a lab report photo. Receptionist only."""
    consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")

    # 1. Read and compress image
    content = await file.read()
    compressed_content = compress_image(content)

    # 2. Upload to Cloudinary
    url = await storage_service.upload_file(
        file_content=compressed_content,
        filename=f"{consultation_id}_report_{uuid.uuid4().hex[:8]}.webp",
        folder="reports"
    )

    if not url:
        raise HTTPException(status_code=500, detail="Failed to upload image to storage")

    # 3. Update database (JSON list)
    current_reports = json.loads(consultation.reports) if consultation.reports else []
    current_reports.append(url)
    consultation.reports = json.dumps(current_reports)
    
    db.commit()
    db.refresh(consultation)
    return consultation
