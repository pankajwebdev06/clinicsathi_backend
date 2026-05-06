"""
Run this ONCE to create all database tables in Supabase PostgreSQL.
Make sure your .env has DATABASE_URL set to the Supabase connection string.

Usage:
    cd clinicflow-backend
    source venv/bin/activate   (Linux/Mac)
    venv\\Scripts\\activate      (Windows)
    python init_db.py
"""
from app.core.database import engine, Base

# Import all models so SQLAlchemy knows about them
from app.features.auth.models import User, Clinic          # noqa: F401
from app.features.patients.models import Patient            # noqa: F401
from app.features.queue.models import QueueEntry            # noqa: F401
from app.features.consultations.models import Consultation  # noqa: F401
from app.features.prescriptions.models import Prescription, PrescriptionMedicine  # noqa: F401

if __name__ == "__main__":
    print("Creating all tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Done! All tables created.")
