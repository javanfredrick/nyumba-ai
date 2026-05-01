"""
FastAPI dependency injection.
Handles auth, tenant isolation, and subscription gate-keeping.
"""
from typing import Annotated
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.core.config import settings
from app.db.session import get_db
from app.models.landlord import Landlord, SubscriptionTier
from app.services.landlord_service import landlord_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token")


async def get_current_landlord(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Landlord:
    """Decode JWT and return the authenticated landlord."""
    payload = decode_access_token(token)
    landlord_id: str = payload.get("landlord_id")
    if not landlord_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    landlord = await landlord_service.get_by_id(db, UUID(landlord_id))
    if not landlord or not landlord.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Landlord not found or inactive")
    return landlord


# Convenience alias
CurrentLandlord = Annotated[Landlord, Depends(get_current_landlord)]
DBSession = Annotated[AsyncSession, Depends(get_db)]


def require_tier(*allowed_tiers: SubscriptionTier):
    """
    Dependency factory: ensure the landlord has one of the required tiers.
    Usage: Depends(require_tier(SubscriptionTier.GROWTH, SubscriptionTier.ENTERPRISE))
    """
    async def _check(landlord: CurrentLandlord):
        if landlord.subscription_tier not in allowed_tiers:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"This feature requires one of: {[t.value for t in allowed_tiers]}",
            )
        return landlord
    return _check


def require_unit_quota():
    """Ensure landlord hasn't exceeded their tier's unit limit."""
    async def _check(landlord: CurrentLandlord, db: DBSession):
        from app.services.property_service import property_service
        unit_count = await property_service.count_units(db, landlord.id)
        limit = settings.TIER_STARTER_MAX_UNITS
        if landlord.subscription_tier == SubscriptionTier.GROWTH:
            limit = settings.TIER_GROWTH_MAX_UNITS
        elif landlord.subscription_tier == SubscriptionTier.ENTERPRISE:
            limit = settings.TIER_ENTERPRISE_MAX_UNITS
        if unit_count >= limit:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Unit quota reached ({unit_count}/{limit}). Please upgrade your plan.",
            )
        return landlord
    return _check
