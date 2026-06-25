"""
app/api/billing.py -- Stripe credit top-up.

Endpoints:
  GET  /api/billing/packages         -- public list of purchasable credit packages
  POST /api/billing/checkout-session -- auth required, creates a Stripe
                                         Checkout Session for a chosen package
  POST /api/billing/webhook          -- Stripe webhook (NO auth -- verified
                                         via Stripe-Signature header instead)
  GET  /api/billing/history          -- auth required, user's past purchases

SECURITY MODEL (read this before touching pricing logic):
  - The price and credit amount for a purchase NEVER come from the client.
    The client only sends a `package_id` (e.g. "starter"); the server looks
    up the actual USD amount + credit count from CREDIT_PACKAGES below.
    This replaces the old app/api/chat.py POST /buy_credits endpoint, which
    let an authenticated client pass arbitrary `amount`/`price` query params
    and credited them with ZERO payment verification -- a live exploit that
    has been removed as part of this change.
  - Credits are only ever added inside the webhook handler, after Stripe's
    signature has been verified, and only once per stripe_session_id (the
    credit_purchases table has a UNIQUE constraint on that column, so even
    if Stripe retries the same event multiple times -- which it does on any
    non-2xx response -- the user cannot be double-credited).

NOTE on stripe-python's StripeObject (bit us once, documenting so it doesn't
happen again): `event["data"]["object"]` returns a StripeObject, not a plain
dict. Bracket access (`obj["id"]`) and `getattr(obj, "id", default)` both
work, but `obj.get("id")` does NOT -- StripeObject's __getattr__ falls
through to `self[k]` for ANY unrecognized attribute name, including "get"
itself, so `session.get(...)` raises AttributeError instead of behaving
like dict.get(). Always use getattr(obj, key, default) on Stripe objects,
never .get(). tests/test_billing.py's signature-verification tests caught
this for real before it ever reached production.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.sql import select, update, desc
from loguru import logger

from app.config import settings
from app.database import engine, users, credit_purchases
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/billing", tags=["billing"])

try:
    import stripe
    _STRIPE_SDK_AVAILABLE = True
except ImportError:
    _STRIPE_SDK_AVAILABLE = False
    logger.warning("⚠️  'stripe' package not installed -- run: pip install stripe")


# ── CREDIT PACKAGES (server-side source of truth -- never trust the client) ─
# credits = price_usd_cents at face value (1 credit ≈ $0.01, matching how
# council.py computes credits_needed = max(1, int(total_cost_usd * 100)))
# plus a volume bonus on the two larger tiers to reward bigger top-ups.
CREDIT_PACKAGES: dict = {
    "starter": {
        "label": "Starter",
        "price_usd_cents": 500,
        "credits": 500,
        "bonus_pct": 0,
    },
    "growth": {
        "label": "Growth",
        "price_usd_cents": 2000,
        "credits": 2200,
        "bonus_pct": 10,
    },
    "scale": {
        "label": "Scale",
        "price_usd_cents": 5000,
        "credits": 6000,
        "bonus_pct": 20,
    },
}


def _require_stripe_configured() -> None:
    if not _STRIPE_SDK_AVAILABLE:
        raise HTTPException(status_code=503, detail="Billing SDK not installed on server")
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Billing not configured (missing STRIPE_SECRET_KEY)")
    stripe.api_key = settings.STRIPE_SECRET_KEY


# ── GET /api/billing/packages ───────────────────────────────────────────────
@router.get("/packages")
async def list_packages():
    """Public -- no auth required. Frontend renders these as buy buttons."""
    return {
        "packages": [
            {
                "id": pid,
                "label": pkg["label"],
                "price_usd": pkg["price_usd_cents"] / 100,
                "credits": pkg["credits"],
                "bonus_pct": pkg["bonus_pct"],
            }
            for pid, pkg in CREDIT_PACKAGES.items()
        ]
    }


# ── POST /api/billing/checkout-session ──────────────────────────────────────
class CheckoutRequest(BaseModel):
    package_id: str


@router.post("/checkout-session")
async def create_checkout_session(
    payload: CheckoutRequest,
    current_user=Depends(get_current_user),
):
    _require_stripe_configured()

    package = CREDIT_PACKAGES.get(payload.package_id)
    if not package:
        raise HTTPException(status_code=400, detail=f"Unknown package_id: {payload.package_id}")

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"Consilium AI -- {package['label']} credit pack",
                        "description": f"{package['credits']} credits",
                    },
                    "unit_amount": package["price_usd_cents"],
                },
                "quantity": 1,
            }],
            success_url=f"{settings.PUBLIC_BASE_URL}/app?billing=success&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.PUBLIC_BASE_URL}/app?billing=cancel",
            client_reference_id=str(current_user.id),
            metadata={"user_id": str(current_user.id), "package_id": payload.package_id},
        )
    except Exception as e:
        logger.error(f"❌ Stripe checkout session creation failed: {e}")
        raise HTTPException(status_code=502, detail="Could not start checkout. Try again shortly.")

    # Record the attempt as "pending" BEFORE redirecting the user to Stripe,
    # so the webhook has a row to find/complete when payment succeeds.
    try:
        with engine.begin() as conn:
            conn.execute(credit_purchases.insert().values(
                user_id=current_user.id,
                stripe_session_id=session.id,
                stripe_payment_intent_id=getattr(session, "payment_intent", None),
                package_id=payload.package_id,
                amount_usd_cents=package["price_usd_cents"],
                credits_purchased=package["credits"],
                status="pending",
                created_at=datetime.utcnow(),
            ))
    except Exception as e:
        # Non-fatal for the user's checkout flow, but means the webhook
        # won't find a row to complete -- log loudly so it's caught.
        logger.error(f"❌ Failed to record pending credit_purchases row: {e}")

    logger.info(f"💳 Checkout session created: user={current_user.id} package={payload.package_id} session={session.id}")
    return {"checkout_url": session.url, "session_id": session.id}


# ── POST /api/billing/webhook ────────────────────────────────────────────────
@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Stripe calls this directly -- there is no user JWT here. Authenticity is
    proven entirely by verifying the Stripe-Signature header against the raw
    request body using STRIPE_WEBHOOK_SECRET. Never parse this as JSON before
    verification -- Stripe signs the exact raw bytes.
    """
    if not _STRIPE_SDK_AVAILABLE or not settings.STRIPE_SECRET_KEY:
        # Returning 503 makes Stripe retry later once billing is configured,
        # rather than permanently dropping the event with a 4xx.
        raise HTTPException(status_code=503, detail="Billing not configured")
    stripe.api_key = settings.STRIPE_SECRET_KEY

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.error("❌ Webhook received but STRIPE_WEBHOOK_SECRET not set -- rejecting")
        raise HTTPException(status_code=503, detail="Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        logger.warning("⚠️  Stripe webhook signature verification failed -- rejecting")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"❌ Webhook payload error: {e}")
        raise HTTPException(status_code=400, detail="Malformed webhook payload")

    if event["type"] != "checkout.session.completed":
        # Ack anything we don't care about so Stripe stops retrying it.
        return {"status": "ignored", "type": event["type"]}

    session = event["data"]["object"]
    # IMPORTANT: use getattr(), not .get() -- see module docstring above.
    session_id = getattr(session, "id", None)
    payment_intent_id = getattr(session, "payment_intent", None)

    with engine.begin() as conn:
        row = conn.execute(
            select(credit_purchases).where(credit_purchases.c.stripe_session_id == session_id)
        ).fetchone()

        if not row:
            logger.warning(f"⚠️  Webhook for unknown session_id={session_id} -- no matching pending row")
            return {"status": "no_matching_purchase"}

        if row.status == "completed":
            # Idempotent no-op: Stripe already got credited for this once.
            logger.info(f"ℹ️  Duplicate webhook for session={session_id}, already completed -- skipping")
            return {"status": "already_completed"}

        conn.execute(
            update(credit_purchases)
            .where(credit_purchases.c.id == row.id)
            .values(status="completed", completed_at=datetime.utcnow(),
                     stripe_payment_intent_id=payment_intent_id)
        )
        conn.execute(
            update(users)
            .where(users.c.id == row.user_id)
            .values(credits=users.c.credits + row.credits_purchased)
        )

    logger.info(
        f"✅ Credits applied: user={row.user_id} package={row.package_id} "
        f"+{row.credits_purchased} credits (session={session_id})"
    )
    return {"status": "completed"}


# ── GET /api/billing/history ─────────────────────────────────────────────────
@router.get("/history")
async def billing_history(limit: int = 20, current_user=Depends(get_current_user)):
    with engine.connect() as conn:
        rows = conn.execute(
            select(credit_purchases)
            .where(credit_purchases.c.user_id == current_user.id)
            .order_by(desc(credit_purchases.c.created_at))
            .limit(min(limit, 100))
        ).fetchall()
    return {
        "purchases": [
            {
                "id": r.id,
                "package_id": r.package_id,
                "amount_usd": r.amount_usd_cents / 100,
                "credits_purchased": r.credits_purchased,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in rows
        ]
    }
