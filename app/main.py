import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, Base

# Import all models so SQLAlchemy knows about them for table creation
from app.features.auth.models import User, Clinic  # noqa: F401
from app.features.patients.models import Patient  # noqa: F401
from app.features.queue.models import QueueEntry  # noqa: F401
from app.features.consultations.models import Consultation  # noqa: F401
from app.features.prescriptions.models import Prescription, PrescriptionMedicine  # noqa: F401
from app.features.admin.models import BlogPost, AdminTeamMember, Subscription  # noqa: F401

app = FastAPI(
    title="ClinicSathi API",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)


# ── CORS (MUST BE FIRST) ───────────────────────────────────────────────────
# In production set ALLOWED_ORIGINS env var to your Vercel domain(s)
DEFAULT_ORIGINS = "https://clinicsathi-frontend.vercel.app,https://clinic-sathi.vercel.app,http://localhost:3000,http://127.0.0.1:3000"

cors_origins_str = settings.ALLOWED_ORIGINS if settings.ALLOWED_ORIGINS and settings.ALLOWED_ORIGINS != "*" else DEFAULT_ORIGINS
origins = [o.strip() for o in cors_origins_str.split(",") if o.strip()]

print(f"🔒 CORS allowed origins: {origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,
)


# ── Database Table Creation ─────────────────────────────────────────────────
def _setup_database():
    """Synchronous database setup function to run in thread."""
    try:
        from sqlalchemy import text
        # Test connection with short timeout
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print(f"✅ Database connected: {result.scalar()}")
        
        # Create tables
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created/verified successfully")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print(f"   DATABASE_URL set: {bool(settings.DATABASE_URL)}")
        if settings.DATABASE_URL and '@' in settings.DATABASE_URL:
            print(f"   Host: {settings.DATABASE_URL.split('@')[-1]}")
        return False

@app.on_event("startup")
async def create_tables():
    """Create all database tables on startup if they don't exist (non-blocking)."""
    # Run in thread pool to not block startup
    asyncio.create_task(asyncio.to_thread(_setup_database))


# ── Security Headers (AFTER CORS) ──────────────────────────────────────────
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    # Skip CORS preflight requests - let CORS middleware handle them
    if request.method == "OPTIONS":
        return await call_next(request)
    
    # Enforce HTTPS if x-forwarded-proto is http
    if request.headers.get("x-forwarded-proto") == "http":
        url = request.url.replace(scheme="https")
        return RedirectResponse(url, status_code=301)
        
    response = await call_next(request)
    
    # Helmet-like headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "same-origin"
    return response

# ── Root route ───────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"message": "Welcome to ClinicSathi API", "docs": "/api/docs", "status": "active"}


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.VERSION}


# ── Run Migrations (for free tier without Shell access) ─────────────────────
@app.post("/run-migrations")
async def run_migrations():
    """Run Alembic migrations. Call this endpoint to update database schema."""
    import subprocess
    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            timeout=60
        )
        return {
            "success": True,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Migration timed out"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Routers ──────────────────────────────────────────────────────────────────
from app.features.patients.router import router as patients_router
from app.features.queue.router import router as queue_router
from app.features.auth.router import router as auth_router
from app.features.consultations.router import router as consultations_router
from app.features.prescriptions.router import router as prescriptions_router
from app.features.admin.router import router as admin_router
from app.features.admin.subscription_router import router as subscription_router

app.include_router(auth_router,          prefix="/api/v1/auth",          tags=["Auth"])
app.include_router(patients_router,      prefix="/api/v1/patients",      tags=["Patients"])
app.include_router(queue_router,         prefix="/api/v1/queue",         tags=["Queue"])
app.include_router(consultations_router, prefix="/api/v1/consultations", tags=["Consultations"])
app.include_router(prescriptions_router, prefix="/api/v1/prescriptions", tags=["Prescriptions"])
app.include_router(admin_router,         prefix="/api/v1/admin",         tags=["Admin"])
app.include_router(subscription_router,  prefix="/api/v1/subscriptions", tags=["Subscriptions"])
