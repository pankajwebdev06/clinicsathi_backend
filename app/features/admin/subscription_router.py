"""
Subscription & Payment Router
Handles:
  POST /subscriptions/plans          - List available plans
  POST /subscriptions/create-order   - Create Cashfree payment order
  POST /subscriptions/verify         - Verify payment after Cashfree redirect
  POST /subscriptions/webhook        - Cashfree payment webhook (server-to-server)
  GET  /subscriptions/status         - Get current subscription status for a clinic
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import uuid
import hmac
import hashlib
import json
import os

from app.core.database import get_db
from app.core.deps import get_current_user
from app.features.auth.models import User
from app.features.admin.models import Subscription, SubscriptionPlan, SubscriptionStatus
from app.services.cashfree_service import (
    create_payment_order,
    verify_payment_order,
    get_all_plans,
)

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    plan: str  # "monthly" | "annual"


class VerifyPaymentRequest(BaseModel):
    order_id: str   # Cashfree order ID returned by create-order


class SubscriptionResponse(BaseModel):
    id: str
    clinic_id: str
    plan: str
    status: str
    amount: float
    total_amount: float
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_active_subscription(clinic_id: str, db: Session) -> Optional[Subscription]:
    """Return active/trial subscription for a clinic, or None."""
    return (
        db.query(Subscription)
        .filter(
            Subscription.clinic_id == clinic_id,
            Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]),
            Subscription.expires_at > datetime.utcnow(),
        )
        .order_by(Subscription.expires_at.desc())
        .first()
    )


def _activate_subscription(sub: Subscription, cf_payment_id: str, db: Session) -> Subscription:
    """Mark subscription as active after successful payment."""
    now = datetime.utcnow()
    sub.status = SubscriptionStatus.ACTIVE
    sub.cf_payment_id = cf_payment_id
    sub.cf_payment_status = "SUCCESS"
    sub.starts_at = now

    if sub.plan == SubscriptionPlan.MONTHLY:
        sub.expires_at = now + timedelta(days=31)
    else:  # annual
        sub.expires_at = now + timedelta(days=366)

    sub.updated_at = now
    db.commit()
    db.refresh(sub)
    return sub


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/plans")
async def list_plans():
    """Return all available subscription plans with pricing."""
    return get_all_plans()


@router.post("/create-order")
async def create_subscription_order(
    body: CreateOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a Cashfree payment order for a subscription plan.

    Returns Cashfree payment_session_id which the frontend uses to open the payment modal.
    """
    if body.plan not in ("monthly", "annual"):
        raise HTTPException(status_code=400, detail="Plan must be 'monthly' or 'annual'.")

    # Check if already has active subscription
    existing = _get_active_subscription(current_user.clinic_id, db)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Active subscription already exists. Expires: {existing.expires_at.date()}",
        )

    # Generate unique order_id
    order_id = f"CS-{uuid.uuid4().hex[:12].upper()}"

    plan_amounts = {"monthly": 599.00, "annual": 5599.00}
    amount = plan_amounts[body.plan]

    # Create Cashfree order
    try:
        cf_result = create_payment_order(
            order_id=order_id,
            plan=body.plan,
            customer_name=current_user.name,
            customer_phone=current_user.mobile_number,
            customer_email=current_user.email,
            clinic_id=current_user.clinic_id,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Save pending subscription record
    subscription = Subscription(
        id=str(uuid.uuid4()),
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        plan=SubscriptionPlan(body.plan),
        status=SubscriptionStatus.PENDING,
        amount=amount,
        gst_amount=0,
        total_amount=amount,
        cf_order_id=cf_result["cf_order_id"],
        cf_order_token=cf_result["payment_session_id"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(subscription)
    db.commit()

    return {
        "order_id": order_id,
        "cf_order_id": cf_result["cf_order_id"],
        "payment_session_id": cf_result["payment_session_id"],
        "amount": amount,
        "plan": body.plan,
        "currency": "INR",
        "environment": os.getenv("CASHFREE_ENV", "TEST"),
    }


@router.post("/verify")
async def verify_subscription_payment(
    body: VerifyPaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Verify payment status after Cashfree redirect.
    Called by frontend after user completes payment.
    """
    # Find the subscription record by Cashfree order ID
    sub = (
        db.query(Subscription)
        .filter(
            Subscription.cf_order_id == body.order_id,
            Subscription.user_id == current_user.id,
        )
        .first()
    )

    if not sub:
        raise HTTPException(status_code=404, detail="Subscription order not found.")

    if sub.status == SubscriptionStatus.ACTIVE:
        return {"status": "already_active", "subscription": SubscriptionResponse.model_validate(sub)}

    # Verify with Cashfree
    try:
        cf_status = verify_payment_order(body.order_id)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    payment_status = cf_status.get("payment_status", "PENDING")

    if payment_status == "SUCCESS":
        sub = _activate_subscription(sub, cf_status.get("cf_payment_id", ""), db)
        return {
            "status": "success",
            "message": "Subscription activated successfully!",
            "subscription": SubscriptionResponse.model_validate(sub),
        }
    elif payment_status == "FAILED":
        sub.status = SubscriptionStatus.CANCELLED
        sub.cf_payment_status = "FAILED"
        sub.updated_at = datetime.utcnow()
        db.commit()
        raise HTTPException(status_code=402, detail="Payment failed. Please try again.")
    else:
        return {
            "status": "pending",
            "message": "Payment is still processing. Please wait.",
            "subscription": SubscriptionResponse.model_validate(sub),
        }


@router.post("/webhook")
async def cashfree_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Cashfree server-to-server webhook endpoint.
    Automatically activates subscriptions after confirmed payment.

    Configure this URL in your Cashfree merchant dashboard under:
    Settings → Webhook → Payment Webhook URL
    """
    # Get raw body for signature verification
    body_bytes = await request.body()
    
    # Verify Cashfree signature
    cf_signature = request.headers.get("x-webhook-signature")
    cf_timestamp = request.headers.get("x-webhook-timestamp")
    cf_secret = os.getenv("CASHFREE_SECRET", "")
    
    if cf_signature and cf_timestamp and cf_secret:
        # Signature verification per Cashfree docs
        message = f"{cf_timestamp}{body_bytes.decode()}"
        computed = hmac.new(
            cf_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        
        if not hmac.compare_digest(computed, cf_signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        data = json.loads(body_bytes)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Extract payment info
    event_type = data.get("type", "")
    payment_data = data.get("data", {})
    order = payment_data.get("order", {})
    payment = payment_data.get("payment", {})

    cf_order_id = order.get("order_id")
    payment_status = payment.get("payment_status")
    cf_payment_id = str(payment.get("cf_payment_id", ""))

    if not cf_order_id:
        return {"status": "ignored", "reason": "No order_id in webhook"}

    # Find subscription
    sub = db.query(Subscription).filter(Subscription.cf_order_id == cf_order_id).first()
    if not sub:
        return {"status": "ignored", "reason": "Order not found in database"}

    if event_type == "PAYMENT_SUCCESS_WEBHOOK" or payment_status == "SUCCESS":
        if sub.status != SubscriptionStatus.ACTIVE:
            _activate_subscription(sub, cf_payment_id, db)

    elif event_type == "PAYMENT_FAILED_WEBHOOK" or payment_status == "FAILED":
        sub.status = SubscriptionStatus.CANCELLED
        sub.cf_payment_status = "FAILED"
        sub.updated_at = datetime.utcnow()
        db.commit()

    return {"status": "ok"}


@router.get("/status")
async def get_subscription_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current subscription status for the logged-in doctor's clinic."""
    active_sub = _get_active_subscription(current_user.clinic_id, db)

    if active_sub:
        return {
            "has_active_subscription": True,
            "subscription": SubscriptionResponse.model_validate(active_sub),
            "days_remaining": (active_sub.expires_at - datetime.utcnow()).days,
        }

    # Check for most recent expired/cancelled
    latest = (
        db.query(Subscription)
        .filter(Subscription.clinic_id == current_user.clinic_id)
        .order_by(Subscription.created_at.desc())
        .first()
    )

    return {
        "has_active_subscription": False,
        "last_subscription": SubscriptionResponse.model_validate(latest) if latest else None,
        "available_plans": get_all_plans(),
    }
