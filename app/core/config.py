from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "ClinicSathi API"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"

    # ─── Database ─────────────────────────────────────────────────────────────
    # Supabase PostgreSQL (set in .env / Render env vars)
    # Format: postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
    DATABASE_URL: str = "sqlite:///./clinicsathi.db"

    # ─── Security ─────────────────────────────────────────────────────────────
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_USE_ENV"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days

    # ─── Admin Panel Credentials (env-based, no OTP) ──────────────────────────
    # Set these in .env and Render/Vercel environment variables
    ADMIN_SECRET_KEY: Optional[str] = None
    ADMIN_PASSWORD: Optional[str] = None

    # ─── Supabase Storage (for image uploads) ─────────────────────────────────
    SUPABASE_URL: Optional[str] = None
    SUPABASE_SERVICE_KEY: Optional[str] = None   # service_role key (not anon)

    # ─── Cloudinary Storage (for image uploads) ───────────────────────────────
    CLOUDINARY_CLOUD_NAME: Optional[str] = None
    CLOUDINARY_API_KEY: Optional[str] = None
    CLOUDINARY_API_SECRET: Optional[str] = None

    # ─── OTP Services ───────────────────────────────────────────────────────────
    # Fast2SMS for India SMS (https://www.fast2sms.com/)
    FAST2SMS_API_KEY: Optional[str] = None
    
    # WhatsApp Business API (Meta)
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = None
    WHATSAPP_ACCESS_TOKEN: Optional[str] = None
    
    # SendGrid for Email
    SENDGRID_API_KEY: Optional[str] = None
    SENDER_EMAIL: str = "noreply@clinicsathi.in"

    # ─── CORS ─────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins. Set in Render env vars for production.
    ALLOWED_ORIGINS: str = "*"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
