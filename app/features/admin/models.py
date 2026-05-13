from sqlalchemy import Column, String, DateTime, Boolean, Text, Enum, Float, Integer
from app.core.database import Base
import enum
from datetime import datetime


class AdminTeamRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    EDITOR = "editor"
    SUPPORT = "support"


class SubscriptionPlan(str, enum.Enum):
    MONTHLY = "monthly"
    ANNUAL = "annual"


class SubscriptionStatus(str, enum.Enum):
    PENDING = "pending"       # Payment initiated
    ACTIVE = "active"         # Payment confirmed
    EXPIRED = "expired"       # Subscription ended
    CANCELLED = "cancelled"   # Cancelled by doctor
    TRIAL = "trial"           # Free trial period


class BlogPost(Base):
    """Blog posts created and published via the Admin CMS."""
    __tablename__ = "blog_posts"

    id = Column(String, primary_key=True)
    title = Column(String(300), nullable=False)
    slug = Column(String(300), nullable=False, unique=True, index=True)
    excerpt = Column(String(600), nullable=True)
    content = Column(Text, nullable=True)           # Markdown content
    category = Column(String(100), nullable=True)
    cover_emoji = Column(String(10), nullable=True, default="📝")
    cover_color_from = Column(String(30), nullable=True, default="#3b82f6")
    cover_color_to = Column(String(30), nullable=True, default="#14b8a6")
    read_time = Column(String(30), nullable=True, default="5 min read")
    published = Column(Boolean, default=False, nullable=False)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AdminTeamMember(Base):
    """Internal ClinicSathi team members with admin panel access."""
    __tablename__ = "admin_team_members"

    id = Column(String, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(200), nullable=False, unique=True)
    role = Column(Enum(AdminTeamRole), nullable=False, default=AdminTeamRole.EDITOR)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Subscription(Base):
    """Doctor/Clinic subscription records. Tracks Cashfree payments."""
    __tablename__ = "subscriptions"

    id = Column(String, primary_key=True)                          # Internal UUID
    clinic_id = Column(String, nullable=False, index=True)         # FK → clinics.id
    user_id = Column(String, nullable=False, index=True)           # FK → users.id (doctor)

    # Plan
    plan = Column(Enum(SubscriptionPlan), nullable=False)          # monthly | annual
    status = Column(Enum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.PENDING)

    # Pricing (INR)
    amount = Column(Float, nullable=False)                         # 599 or 5599
    gst_amount = Column(Float, nullable=True, default=0)           # GST (if applicable)
    total_amount = Column(Float, nullable=False)                   # Final charged amount

    # Cashfree fields
    cf_order_id = Column(String(200), nullable=True, index=True)   # Cashfree Order ID
    cf_payment_id = Column(String(200), nullable=True)             # Cashfree Payment ID
    cf_order_token = Column(String(500), nullable=True)            # Payment session token
    cf_payment_status = Column(String(50), nullable=True)          # SUCCESS | FAILED | PENDING

    # Dates
    starts_at = Column(DateTime, nullable=True)                    # When subscription starts
    expires_at = Column(DateTime, nullable=True)                   # When subscription expires
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
