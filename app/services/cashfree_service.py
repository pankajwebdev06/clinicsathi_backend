"""
Cashfree Payment Gateway Service
Docs: https://docs.cashfree.com/docs/payment-gateway

Environment Variables Required:
  CASHFREE_APP_ID   - Your Cashfree App ID
  CASHFREE_SECRET   - Your Cashfree Secret Key
  CASHFREE_ENV      - 'PROD' or 'TEST' (default: TEST)
  FRONTEND_URL      - Frontend base URL for redirect (e.g. https://clinicsathi.vercel.app)
"""

import os
import uuid
import requests
from typing import Optional
from datetime import datetime


CASHFREE_ENV = os.getenv("CASHFREE_ENV", "TEST")

# API base URLs
CASHFREE_BASE_URL = (
    "https://api.cashfree.com/pg"
    if CASHFREE_ENV == "PROD"
    else "https://sandbox.cashfree.com/pg"
)

# Subscription Pricing (INR)
PLAN_PRICES = {
    "monthly": {
        "amount": 599.00,
        "display": "₹599/month",
        "description": "ClinicSathi Monthly Subscription",
    },
    "annual": {
        "amount": 5599.00,
        "display": "₹5599/year (Save ₹1589!)",
        "description": "ClinicSathi Annual Subscription",
    },
}


def _get_headers() -> dict:
    """Get Cashfree API headers."""
    app_id = os.getenv("CASHFREE_APP_ID")
    secret = os.getenv("CASHFREE_SECRET")

    if not app_id or not secret:
        raise ValueError(
            "CASHFREE_APP_ID and CASHFREE_SECRET must be set in environment variables. "
            "Register at https://merchant.cashfree.com to get credentials."
        )

    return {
        "Content-Type": "application/json",
        "x-client-id": app_id,
        "x-client-secret": secret,
        "x-api-version": "2023-08-01",
    }


def create_payment_order(
    order_id: str,
    plan: str,
    customer_name: str,
    customer_phone: str,
    customer_email: Optional[str],
    clinic_id: str,
    user_id: str,
) -> dict:
    """
    Create a Cashfree payment order for a subscription.

    Returns:
        {
            "cf_order_id": "...",
            "payment_session_id": "...",
            "order_status": "ACTIVE",
            "amount": 599.0,
            "plan": "monthly"
        }
    """
    if plan not in PLAN_PRICES:
        raise ValueError(f"Invalid plan: {plan}. Must be 'monthly' or 'annual'.")

    plan_info = PLAN_PRICES[plan]
    amount = plan_info["amount"]

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

    payload = {
        "order_id": order_id,
        "order_amount": amount,
        "order_currency": "INR",
        "order_note": f"{plan_info['description']} for clinic {clinic_id}",
        "customer_details": {
            "customer_id": user_id,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "customer_email": customer_email or f"{user_id}@clinicsathi.in",
        },
        "order_meta": {
            "return_url": f"{frontend_url}/subscription/success?order_id={order_id}",
            "notify_url": f"{os.getenv('BACKEND_URL', 'http://localhost:8000')}/api/v1/subscriptions/webhook",
        },
        "order_tags": {
            "clinic_id": clinic_id,
            "user_id": user_id,
            "plan": plan,
        },
    }

    try:
        response = requests.post(
            f"{CASHFREE_BASE_URL}/orders",
            json=payload,
            headers=_get_headers(),
            timeout=15,
        )
        result = response.json()

        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"Cashfree order creation failed: {result.get('message', 'Unknown error')}"
            )

        return {
            "cf_order_id": result["cf_order_id"],
            "payment_session_id": result["payment_session_id"],
            "order_status": result["order_status"],
            "amount": amount,
            "plan": plan,
        }

    except requests.RequestException as e:
        raise RuntimeError(f"Network error calling Cashfree: {e}")


def verify_payment_order(cf_order_id: str) -> dict:
    """
    Verify payment status from Cashfree by order ID.

    Returns:
        {
            "order_status": "PAID" | "ACTIVE" | "EXPIRED",
            "cf_payment_id": "...",
            "payment_status": "SUCCESS" | "FAILED" | "PENDING"
        }
    """
    try:
        response = requests.get(
            f"{CASHFREE_BASE_URL}/orders/{cf_order_id}/payments",
            headers=_get_headers(),
            timeout=15,
        )
        result = response.json()

        if response.status_code != 200:
            raise RuntimeError(
                f"Cashfree verification failed: {result.get('message', 'Unknown error')}"
            )

        # result is a list of payment objects
        if not result:
            return {"order_status": "ACTIVE", "cf_payment_id": None, "payment_status": "PENDING"}

        # Get the most recent payment
        latest = result[-1]
        return {
            "order_status": latest.get("order_status", "UNKNOWN"),
            "cf_payment_id": str(latest.get("cf_payment_id", "")),
            "payment_status": latest.get("payment_status", "PENDING"),  # SUCCESS | FAILED | PENDING
        }

    except requests.RequestException as e:
        raise RuntimeError(f"Network error calling Cashfree: {e}")


def get_plan_info(plan: str) -> dict:
    """Get pricing info for a plan."""
    if plan not in PLAN_PRICES:
        raise ValueError(f"Invalid plan: {plan}")
    return PLAN_PRICES[plan]


def get_all_plans() -> dict:
    """Return all available plans with pricing."""
    return {
        "monthly": {
            **PLAN_PRICES["monthly"],
            "plan_key": "monthly",
            "billing_cycle": "Billed every month",
            "savings": None,
        },
        "annual": {
            **PLAN_PRICES["annual"],
            "plan_key": "annual",
            "billing_cycle": "Billed once per year",
            "savings": "Save ₹1,589 vs monthly",
            "monthly_equivalent": round(5599 / 12, 0),
        },
    }
