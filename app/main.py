from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

app = FastAPI(
    title="ClinicSathi API",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# ── CORS ────────────────────────────────────────────────────────────────────
# In production set ALLOWED_ORIGINS env var to your Vercel domain(s)
# e.g. "https://clinicsathi.vercel.app,https://www.clinicsathi.in"
origins = (
    [o.strip() for o in settings.ALLOWED_ORIGINS.split(",")]
    if settings.ALLOWED_ORIGINS != "*"
    else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Root route ───────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"message": "Welcome to ClinicSathi API", "docs": "/api/docs", "status": "active"}


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.VERSION}


# ── Routers ──────────────────────────────────────────────────────────────────
from app.features.patients.router import router as patients_router
from app.features.queue.router import router as queue_router
from app.features.auth.router import router as auth_router
from app.features.consultations.router import router as consultations_router
from app.features.prescriptions.router import router as prescriptions_router

app.include_router(auth_router,          prefix="/api/v1/auth",          tags=["Auth"])
app.include_router(patients_router,      prefix="/api/v1/patients",      tags=["Patients"])
app.include_router(queue_router,         prefix="/api/v1/queue",         tags=["Queue"])
app.include_router(consultations_router, prefix="/api/v1/consultations", tags=["Consultations"])
app.include_router(prescriptions_router, prefix="/api/v1/prescriptions", tags=["Prescriptions"])
