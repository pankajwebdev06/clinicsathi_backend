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


def generate_unique_slug(doctor_name: str, city: Optional[str] = None, db: Optional[Session] = None) -> str:
    """Generate a unique slug for a clinic profile."""
    base_slug = generate_slug(doctor_name)
    if city:
        base_slug = f"{base_slug}-{generate_slug(city)}"
    
    # If no database session, return base slug (for testing)
    if not db:
        return base_slug
    
    # Check if slug exists, append number if needed
    counter = 1
    unique_slug = base_slug
    while db.query(Clinic).filter(Clinic.slug == unique_slug).first():
        unique_slug = f"{base_slug}-{counter}"
        counter += 1
    
    return unique_slug
