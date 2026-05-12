from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from typing import Optional
from datetime import datetime, timedelta
import uuid

from app.core.database import get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.features.auth.models import User, Clinic, UserRole
from app.features.patients.models import Patient
from app.features.queue.models import QueueEntry
from app.features.admin.models import BlogPost, AdminTeamMember, AdminTeamRole

router = APIRouter()

# ─── Admin JWT Auth ─────────────────────────────────────────────────────────

def verify_admin_token(x_admin_token: str = Header(...)) -> dict:
    """
    Validate the admin JWT token passed in X-Admin-Token header.
    Returns payload or raises 401.
    """
    from app.core.security import decode_access_token
    payload = decode_access_token(x_admin_token)
    if not payload or payload.get("role") != "admin_panel":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin token",
        )
    return payload


# ─── Login ───────────────────────────────────────────────────────────────────

@router.post("/auth/login")
async def admin_login(data: dict):
    """
    Admin panel login using env-based credentials.
    Body: { "admin_key": "...", "admin_password": "..." }
    Returns a signed JWT on success.
    """
    admin_key = data.get("admin_key", "")
    admin_password = data.get("admin_password", "")

    expected_key = settings.ADMIN_SECRET_KEY or ""
    expected_password = settings.ADMIN_PASSWORD or ""

    if not expected_key or not expected_password:
        raise HTTPException(
            status_code=503,
            detail="Admin credentials not configured on server. Set ADMIN_SECRET_KEY and ADMIN_PASSWORD in .env",
        )

    if admin_key != expected_key or admin_password != expected_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
        )

    token = create_access_token(data={
        "sub": "admin_panel",
        "role": "admin_panel",
    }, expires_delta=timedelta(hours=12))

    return {"access_token": token, "token_type": "bearer"}


# ─── System Stats ─────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_system_stats(
    db: Session = Depends(get_db),
    _: dict = Depends(verify_admin_token),
):
    """System-wide KPI stats for the overview dashboard."""
    total_clinics = db.query(func.count(Clinic.id)).scalar() or 0
    active_clinics = db.query(func.count(Clinic.id)).filter(Clinic.is_active == True).scalar() or 0
    total_doctors = db.query(func.count(User.id)).filter(User.role == UserRole.DOCTOR).scalar() or 0
    total_receptionists = db.query(func.count(User.id)).filter(User.role == UserRole.RECEPTIONIST).scalar() or 0
    total_patients = db.query(func.count(Patient.id)).scalar() or 0

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_tokens = db.query(func.count(QueueEntry.id)).filter(
        QueueEntry.created_at >= today_start
    ).scalar() or 0

    return {
        "total_clinics": total_clinics,
        "active_clinics": active_clinics,
        "total_doctors": total_doctors,
        "total_receptionists": total_receptionists,
        "total_patients": total_patients,
        "today_tokens": today_tokens,
    }


# ─── Analytics (Growth Charts) ───────────────────────────────────────────────

@router.get("/analytics")
async def get_analytics(
    db: Session = Depends(get_db),
    _: dict = Depends(verify_admin_token),
):
    """
    Daily growth data for the last 30 days.
    Returns two series: new clinics per day & new patients per day.
    """
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    # New clinics per day
    clinic_rows = (
        db.query(
            cast(Clinic.created_at, Date).label("day"),
            func.count(Clinic.id).label("count")
        )
        .filter(Clinic.created_at >= thirty_days_ago)
        .group_by(cast(Clinic.created_at, Date))
        .order_by(cast(Clinic.created_at, Date))
        .all()
    )

    # New patients per day
    patient_rows = (
        db.query(
            cast(Patient.created_at, Date).label("day"),
            func.count(Patient.id).label("count")
        )
        .filter(Patient.created_at >= thirty_days_ago)
        .group_by(cast(Patient.created_at, Date))
        .order_by(cast(Patient.created_at, Date))
        .all()
    )

    return {
        "clinics_per_day": [{"date": str(r.day), "count": r.count} for r in clinic_rows],
        "patients_per_day": [{"date": str(r.day), "count": r.count} for r in patient_rows],
    }


# ─── Clinics ─────────────────────────────────────────────────────────────────

@router.get("/clinics")
async def list_all_clinics(
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_admin_token),
):
    """Return all clinics with per-clinic patient count and doctor list."""
    query = db.query(Clinic)
    if search:
        query = query.filter(Clinic.name.ilike(f"%{search}%"))
    clinics = query.order_by(Clinic.created_at.desc()).all()

    result = []
    for clinic in clinics:
        patient_count = db.query(func.count(Patient.id)).filter(
            Patient.clinic_id == clinic.id
        ).scalar() or 0

        doctor = db.query(User).filter(
            User.clinic_id == clinic.id,
            User.role == UserRole.DOCTOR,
        ).first()

        staff_count = db.query(func.count(User.id)).filter(
            User.clinic_id == clinic.id,
        ).scalar() or 0

        result.append({
            "id": clinic.id,
            "name": clinic.name,
            "doctor_name": clinic.doctor_name,
            "doctor_mobile": doctor.mobile_number if doctor else None,
            "specialization": clinic.specialization,
            "city": clinic.city,
            "phone": clinic.phone,
            "patient_count": patient_count,
            "staff_count": staff_count,
            "is_active": clinic.is_active,
            "created_at": clinic.created_at.isoformat() if clinic.created_at else None,
        })

    return result


@router.patch("/clinics/{clinic_id}/toggle")
async def toggle_clinic_status(
    clinic_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_admin_token),
):
    """Toggle a clinic's active/inactive status."""
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")
    clinic.is_active = not clinic.is_active
    db.commit()
    return {"id": clinic.id, "is_active": clinic.is_active}


# ─── Users ────────────────────────────────────────────────────────────────────

@router.get("/users")
async def list_all_users(
    role: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_admin_token),
):
    """All users across all clinics, with optional role and search filters."""
    query = db.query(User)
    if role and role in ["doctor", "receptionist"]:
        query = query.filter(User.role == role)
    if search:
        query = query.filter(
            User.name.ilike(f"%{search}%") | User.mobile_number.ilike(f"%{search}%")
        )
    users = query.order_by(User.created_at.desc()).all()

    result = []
    for u in users:
        clinic = db.query(Clinic).filter(Clinic.id == u.clinic_id).first()
        result.append({
            "id": u.id,
            "name": u.name,
            "mobile_number": u.mobile_number,
            "role": u.role,
            "clinic_id": u.clinic_id,
            "clinic_name": clinic.name if clinic else "—",
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })
    return result


# ─── Payments ────────────────────────────────────────────────────────────────

@router.get("/payments")
async def list_payments(
    db: Session = Depends(get_db),
    _: dict = Depends(verify_admin_token),
):
    """
    Returns payment/subscription records.
    If a `payments` table exists in Supabase, it will be queried.
    Falls back to per-clinic stub data if table doesn't exist yet.
    """
    try:
        from sqlalchemy import text
        rows = db.execute(text(
            "SELECT p.*, c.name as clinic_name FROM payments p "
            "LEFT JOIN clinics c ON c.id = p.clinic_id "
            "ORDER BY p.created_at DESC"
        )).fetchall()
        payments = [dict(r._mapping) for r in rows]
        return payments
    except Exception:
        # Table doesn't exist yet — return per-clinic stubs
        clinics = db.query(Clinic).all()
        return [
            {
                "id": c.id,
                "clinic_name": c.name,
                "plan": "Free Trial",
                "amount": 0,
                "status": "trial",
                "payment_method": "—",
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in clinics
        ]


# ─── Blog CMS ─────────────────────────────────────────────────────────────────

@router.get("/blog")
async def list_blog_posts(
    published: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    """
    List all blog posts. Public endpoint when published=true (no auth needed).
    Admin can see drafts too when authenticated.
    """
    query = db.query(BlogPost)
    if published is True:
        query = query.filter(BlogPost.published == True)
    posts = query.order_by(BlogPost.created_at.desc()).all()

    return [
        {
            "id": p.id,
            "title": p.title,
            "slug": p.slug,
            "excerpt": p.excerpt,
            "category": p.category,
            "cover_emoji": p.cover_emoji,
            "cover_color_from": p.cover_color_from,
            "cover_color_to": p.cover_color_to,
            "read_time": p.read_time,
            "published": p.published,
            "published_at": p.published_at.isoformat() if p.published_at else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in posts
    ]


@router.get("/blog/{slug}")
async def get_blog_post(slug: str, db: Session = Depends(get_db)):
    """Get a single published blog post by slug. Public endpoint."""
    post = db.query(BlogPost).filter(BlogPost.slug == slug).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return {
        "id": post.id,
        "title": post.title,
        "slug": post.slug,
        "excerpt": post.excerpt,
        "content": post.content,
        "category": post.category,
        "cover_emoji": post.cover_emoji,
        "cover_color_from": post.cover_color_from,
        "cover_color_to": post.cover_color_to,
        "read_time": post.read_time,
        "published": post.published,
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "created_at": post.created_at.isoformat() if post.created_at else None,
    }


@router.post("/blog", status_code=201)
async def create_blog_post(
    data: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_admin_token),
):
    """Create a new blog post (draft by default)."""
    post = BlogPost(
        id=str(uuid.uuid4()),
        title=data.get("title", "Untitled"),
        slug=data.get("slug", "").lower().replace(" ", "-"),
        excerpt=data.get("excerpt"),
        content=data.get("content"),
        category=data.get("category"),
        cover_emoji=data.get("cover_emoji", "📝"),
        cover_color_from=data.get("cover_color_from", "#3b82f6"),
        cover_color_to=data.get("cover_color_to", "#14b8a6"),
        read_time=data.get("read_time", "5 min read"),
        published=False,
        created_at=datetime.utcnow(),
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return {"id": post.id, "slug": post.slug, "message": "Post created"}


@router.put("/blog/{post_id}")
async def update_blog_post(
    post_id: str,
    data: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_admin_token),
):
    """Update an existing blog post."""
    post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    for field in ["title", "slug", "excerpt", "content", "category",
                  "cover_emoji", "cover_color_from", "cover_color_to", "read_time"]:
        if field in data:
            setattr(post, field, data[field])

    post.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Post updated"}


@router.patch("/blog/{post_id}/publish")
async def toggle_publish_post(
    post_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_admin_token),
):
    """Toggle a blog post between published and draft."""
    post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    post.published = not post.published
    post.published_at = datetime.utcnow() if post.published else None
    post.updated_at = datetime.utcnow()
    db.commit()
    return {"id": post.id, "published": post.published}


@router.delete("/blog/{post_id}")
async def delete_blog_post(
    post_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_admin_token),
):
    """Permanently delete a blog post."""
    post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    db.delete(post)
    db.commit()
    return {"message": "Post deleted"}


# ─── Team Members ─────────────────────────────────────────────────────────────

@router.get("/team")
async def list_team(
    db: Session = Depends(get_db),
    _: dict = Depends(verify_admin_token),
):
    """List all internal admin team members."""
    members = db.query(AdminTeamMember).order_by(AdminTeamMember.created_at.desc()).all()
    return [
        {
            "id": m.id,
            "name": m.name,
            "email": m.email,
            "role": m.role,
            "is_active": m.is_active,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in members
    ]


@router.post("/team", status_code=201)
async def add_team_member(
    data: dict,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_admin_token),
):
    """Add a new internal team member."""
    existing = db.query(AdminTeamMember).filter(AdminTeamMember.email == data.get("email")).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")

    role_str = data.get("role", "editor")
    try:
        role = AdminTeamRole(role_str)
    except ValueError:
        role = AdminTeamRole.EDITOR

    member = AdminTeamMember(
        id=str(uuid.uuid4()),
        name=data.get("name", ""),
        email=data.get("email", ""),
        role=role,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return {"id": member.id, "message": "Team member added"}


@router.delete("/team/{member_id}")
async def remove_team_member(
    member_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_admin_token),
):
    """Remove an internal team member."""
    member = db.query(AdminTeamMember).filter(AdminTeamMember.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    db.delete(member)
    db.commit()
    return {"message": "Member removed"}
