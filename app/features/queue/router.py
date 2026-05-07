from fastapi import APIRouter, Depends, HTTPException, status, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
from datetime import datetime

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.features.auth.models import User
from app.features.queue.models import QueueEntry, QueueStatus
from app.features.queue.schemas import QueueEntryCreate, QueueEntryUpdate, QueueEntryResponse
from app.core.ws_manager import manager

router = APIRouter()


# ── WebSocket ────────────────────────────────────────────
@router.websocket("/ws/{clinic_id}")
async def queue_websocket(websocket: WebSocket, clinic_id: str):
    await manager.connect(clinic_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(clinic_id, websocket)


# ── CREATE ──────────────────────────────────────────────
@router.post("/", response_model=QueueEntryResponse, status_code=status.HTTP_201_CREATED)
async def add_to_queue(
    data: QueueEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("doctor", "receptionist")),
):
    """Add a patient to the queue. Token is auto-generated."""
    token = _generate_token(db, data.clinic_id)

    entry = QueueEntry(
        id=str(uuid.uuid4()),
        clinic_id=data.clinic_id,
        patient_id=data.patient_id,
        token_number=token,
        status=QueueStatus.WAITING,
        priority=data.priority,
        symptoms=data.symptoms,
        bp=data.bp,
        weight=data.weight,
        temperature=data.temperature,
        pulse=data.pulse,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    # Broadcast update to all clinic devices via WebSocket
    await manager.broadcast_to_clinic(data.clinic_id, {
        "event": "QUEUE_UPDATED",
        "message": f"New patient added: {token}",
        "entry_id": entry.id
    })

    return entry


# ── READ (list) ─────────────────────────────────────────
@router.get("/", response_model=List[QueueEntryResponse])
async def get_queue(
    clinic_id: str,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("doctor", "receptionist")),
):
    """Get the queue for a clinic. Doctor or receptionist."""
    query = db.query(QueueEntry).filter(QueueEntry.clinic_id == clinic_id)

    if status_filter:
        query = query.filter(QueueEntry.status == status_filter)

    return query.order_by(QueueEntry.priority.desc(), QueueEntry.created_at.asc()).all()


# ── UPDATE (change status / priority) ───────────────────
@router.patch("/{entry_id}", response_model=QueueEntryResponse)
async def update_queue_entry(
    entry_id: str,
    data: QueueEntryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("doctor", "receptionist")),
):
    """Update a queue entry's status or priority. Doctor or receptionist."""
    entry = db.query(QueueEntry).filter(QueueEntry.id == entry_id, QueueEntry.clinic_id == current_user.clinic_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Queue entry not found")

    if data.status is not None:
        entry.status = data.status
    if data.priority is not None:
        entry.priority = data.priority

    entry.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(entry)

    # Broadcast update to all clinic devices
    await manager.broadcast_to_clinic(entry.clinic_id, {
        "event": "QUEUE_UPDATED",
        "message": f"Queue status changed for token {entry.token_number}",
        "entry_id": entry.id
    })

    return entry


# ── DELETE ──────────────────────────────────────────────
@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_queue(
    entry_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("receptionist")),
):
    """Remove a patient from the queue. Receptionist only."""
    entry = db.query(QueueEntry).filter(QueueEntry.id == entry_id, QueueEntry.clinic_id == current_user.clinic_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Queue entry not found")

    clinic_id = entry.clinic_id
    token_number = entry.token_number
    db.delete(entry)
    db.commit()

    # Broadcast update to all clinic devices
    await manager.broadcast_to_clinic(clinic_id, {
        "event": "QUEUE_UPDATED",
        "message": f"Patient removed from queue: {token_number}",
        "entry_id": entry_id
    })


# ── HELPER ──────────────────────────────────────────────
def _generate_token(db: Session, clinic_id: str) -> str:
    """Auto-generate the next token number for a clinic (e.g. M-001, M-002...)."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    last_entry = db.query(QueueEntry).filter(
        QueueEntry.clinic_id == clinic_id,
        QueueEntry.created_at >= today_start
    ).order_by(QueueEntry.created_at.desc()).first()

    if not last_entry:
        return "M-001"
    
    try:
        last_num = int(last_entry.token_number.split("-")[1])
        return f"M-{last_num + 1:03d}"
    except (ValueError, IndexError):
        count = db.query(QueueEntry).filter(
            QueueEntry.clinic_id == clinic_id,
            QueueEntry.created_at >= today_start
        ).count()
        return f"M-{count + 1:03d}"
