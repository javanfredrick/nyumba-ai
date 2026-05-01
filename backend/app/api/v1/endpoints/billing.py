"""
Billing Router — /api/v1/billing
Handles Stripe subscription creation, portal, webhooks, and tier upgrades.
"""
import stripe
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.config import settings
from app.core.dependencies import get_db, CurrentLandlord
from app.models.landlord import SubscriptionTier

log = structlog.get_logger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter(prefix="/billing", tags=["Billing"])

# ── Stripe Price IDs — set these in your Stripe Dashboard ────────────────────
# Create products + prices in Stripe, then paste the price IDs below.
TIER_PRICE_IDS = {
    SubscriptionTier.STARTER:    "price_STARTER_PRICE_ID",    # e.g. KES 2,500/mo
    SubscriptionTier.GROWTH:     "price_GROWTH_PRICE_ID",     # e.g. KES 7,500/mo
    SubscriptionTier.ENTERPRISE: "price_ENTERPRISE_PRICE_ID", # e.g. KES 20,000/mo
}

TIER_NAMES = {
    "price_STARTER_PRICE_ID":    SubscriptionTier.STARTER,
    "price_GROWTH_PRICE_ID":     SubscriptionTier.GROWTH,
    "price_ENTERPRISE_PRICE_ID": SubscriptionTier.ENTERPRISE,
}


# ── Create / upgrade subscription ────────────────────────────────────────────

@router.post("/subscribe/{tier}")
async def create_subscription(
    tier: SubscriptionTier,
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a Stripe Checkout Session for a given tier.
    Returns a checkout URL the frontend redirects to.
    """
    price_id = TIER_PRICE_IDS.get(tier)
    if not price_id:
        raise HTTPException(status_code=400, detail="Invalid tier.")

    # Get or create Stripe customer
    customer_id = landlord.stripe_customer_id
    if not customer_id:
        customer = stripe.Customer.create(
            email=landlord.email,
            name=landlord.full_name,
            metadata={"landlord_id": str(landlord.id)},
        )
        customer_id = customer.id
        landlord.stripe_customer_id = customer_id
        await db.commit()

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=f"{settings.APP_BASE_URL}/dashboard?upgrade=success",
        cancel_url=f"{settings.APP_BASE_URL}/dashboard?upgrade=cancelled",
        metadata={"landlord_id": str(landlord.id), "tier": tier.value},
    )
    return {"checkout_url": session.url, "session_id": session.id}


# ── Customer portal (manage / cancel subscription) ───────────────────────────

@router.post("/portal")
async def billing_portal(landlord: CurrentLandlord = Depends()):
    """Return a Stripe Billing Portal URL for the landlord to manage their plan."""
    if not landlord.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No active subscription found.")

    session = stripe.billing_portal.Session.create(
        customer=landlord.stripe_customer_id,
        return_url=f"{settings.APP_BASE_URL}/dashboard",
    )
    return {"portal_url": session.url}


# ── Current subscription info ─────────────────────────────────────────────────

@router.get("/status")
async def billing_status(landlord: CurrentLandlord = Depends()):
    """Return current subscription tier and usage."""
    return {
        "tier": landlord.subscription_tier,
        "stripe_customer_id": landlord.stripe_customer_id,
        "subscription_id": landlord.stripe_subscription_id,
        "expires_at": landlord.subscription_expires_at,
        "ai_tokens_used": landlord.ai_tokens_used,
        "ai_tokens_limit": landlord.ai_tokens_limit,
    }


# ── Stripe Webhook ────────────────────────────────────────────────────────────

@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="stripe-signature"),
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Stripe webhook events to update subscription tiers.
    Stripe signs every webhook — we verify the signature to prevent forgery.
    """
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        log.warning("stripe.webhook_invalid_signature")
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    event_type = event["type"]
    log.info("stripe.webhook_received", event_type=event_type)

    # ── Subscription activated / updated ────────────────────────────────────
    if event_type in ("customer.subscription.created", "customer.subscription.updated"):
        sub = event["data"]["object"]
        await _handle_subscription_update(db, sub)

    # ── Subscription cancelled / ended ───────────────────────────────────────
    elif event_type == "customer.subscription.deleted":
        sub = event["data"]["object"]
        await _handle_subscription_cancelled(db, sub)

    # ── Checkout completed ───────────────────────────────────────────────────
    elif event_type == "checkout.session.completed":
        session = event["data"]["object"]
        if session.get("mode") == "subscription":
            landlord_id = session.get("metadata", {}).get("landlord_id")
            tier_value = session.get("metadata", {}).get("tier")
            if landlord_id and tier_value:
                await _upgrade_landlord_tier(db, landlord_id, tier_value)

    return {"received": True}


# ── Internal webhook helpers ──────────────────────────────────────────────────

async def _handle_subscription_update(db: AsyncSession, sub: dict):
    from sqlalchemy import select
    from app.models.landlord import Landlord
    from datetime import datetime, timezone

    customer_id = sub.get("customer")
    result = await db.execute(
        select(Landlord).where(Landlord.stripe_customer_id == customer_id)
    )
    landlord = result.scalar_one_or_none()
    if not landlord:
        return

    # Map the price ID back to our tier
    items = sub.get("items", {}).get("data", [])
    if items:
        price_id = items[0].get("price", {}).get("id")
        new_tier = TIER_NAMES.get(price_id)
        if new_tier:
            landlord.subscription_tier = new_tier

    landlord.stripe_subscription_id = sub.get("id")

    # Set token limits by tier
    token_limits = {
        SubscriptionTier.STARTER:    100_000,
        SubscriptionTier.GROWTH:     500_000,
        SubscriptionTier.ENTERPRISE: 5_000_000,
    }
    landlord.ai_tokens_limit = token_limits.get(landlord.subscription_tier, 100_000)

    period_end = sub.get("current_period_end")
    if period_end:
        landlord.subscription_expires_at = datetime.fromtimestamp(period_end, tz=timezone.utc)

    await db.commit()
    log.info("stripe.subscription_updated", landlord_id=str(landlord.id), tier=landlord.subscription_tier)


async def _handle_subscription_cancelled(db: AsyncSession, sub: dict):
    from sqlalchemy import select
    from app.models.landlord import Landlord

    customer_id = sub.get("customer")
    result = await db.execute(
        select(Landlord).where(Landlord.stripe_customer_id == customer_id)
    )
    landlord = result.scalar_one_or_none()
    if not landlord:
        return

    landlord.subscription_tier = SubscriptionTier.STARTER
    landlord.stripe_subscription_id = None
    landlord.ai_tokens_limit = 100_000
    await db.commit()
    log.info("stripe.subscription_cancelled", landlord_id=str(landlord.id))


async def _upgrade_landlord_tier(db: AsyncSession, landlord_id: str, tier_value: str):
    from sqlalchemy import select
    from app.models.landlord import Landlord
    from uuid import UUID

    result = await db.execute(
        select(Landlord).where(Landlord.id == UUID(landlord_id))
    )
    landlord = result.scalar_one_or_none()
    if not landlord:
        return

    try:
        landlord.subscription_tier = SubscriptionTier(tier_value)
    except ValueError:
        pass

    await db.commit()
