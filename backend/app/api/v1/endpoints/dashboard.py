"""Dashboard Router — /api/v1/dashboard"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, CurrentLandlord
from app.schemas.schemas import DashboardStats
from app.services.property_service import property_service
from app.services.payment_service import payment_service
from app.services.landlord_service import landlord_service
from sqlalchemy import select, func
from app.models.landlord import Tenant

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def get_stats(
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    prop_stats = await property_service.get_dashboard_stats(db, landlord.id)
    monthly_collected = await payment_service.monthly_collected(db, landlord.id)
    pending_flags = await payment_service.pending_flags_count(db, landlord.id)

    tenant_count = (
        await db.execute(
            select(func.count(Tenant.id)).where(
                Tenant.landlord_id == landlord.id,
                Tenant.is_active == True,
            )
        )
    ).scalar_one()

    total_units = prop_stats["total_units"]
    occupied = prop_stats["occupied_units"]
    expected = prop_stats["monthly_expected_revenue"]
    collection_rate = (
        round(float(monthly_collected) / float(expected) * 100, 1)
        if expected and float(expected) > 0
        else 0.0
    )

    return DashboardStats(
        total_properties=prop_stats["total_properties"],
        total_units=total_units,
        occupied_units=occupied,
        vacant_units=total_units - occupied,
        total_tenants=tenant_count,
        monthly_expected_revenue=expected,
        monthly_collected_revenue=monthly_collected,
        collection_rate=collection_rate,
        pending_flags=pending_flags,
        ai_tokens_used=landlord.ai_tokens_used,
        ai_tokens_limit=landlord.ai_tokens_limit,
    )
