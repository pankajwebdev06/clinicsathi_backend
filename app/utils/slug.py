import re
from typing import Optional
from sqlalchemy.orm import Session
from app.features.auth.models import Clinic


def generate_slug(text: str) -> str:
    """Generate a URL-friendly slug from text."""
    # Convert to lowercase
    slug = text.lower()
    # Replace spaces and special chars with hyphens
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s-]+', '-', slug)
    slug = slug.strip('-')
    return slug


def generate_unique_slug(
    doctor_name: str,
    city: Optional[str] = None,
    specialization: Optional[str] = None,
    db: Optional[Session] = None,
    exclude_clinic_id: Optional[str] = None,
) -> str:
    """Generate a unique slug for a clinic profile.

    Format: doctor-name-specialization-city (with specialization in the middle,
    matching the frontend's slug shape).
    """
    parts = [generate_slug(doctor_name)]
    if specialization:
        spec_slug = generate_slug(specialization)
        if spec_slug:
            parts.append(spec_slug)
    if city:
        city_slug = generate_slug(city)
        if city_slug:
            parts.append(city_slug)
    base_slug = "-".join(p for p in parts if p)

    # If no database session, return base slug (for testing)
    if not db:
        return base_slug

    # Check if slug exists, append number if needed (ignore the current clinic
    # when updating an existing record so it doesn't conflict with itself)
    counter = 1
    unique_slug = base_slug
    while True:
        q = db.query(Clinic).filter(Clinic.slug == unique_slug)
        if exclude_clinic_id:
            q = q.filter(Clinic.id != exclude_clinic_id)
        if not q.first():
            break
        unique_slug = f"{base_slug}-{counter}"
        counter += 1

    return unique_slug
