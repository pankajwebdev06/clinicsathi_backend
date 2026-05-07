from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
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


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
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
