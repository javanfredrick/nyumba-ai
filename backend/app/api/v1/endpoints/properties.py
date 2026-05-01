"""Properties & Units Router — /api/v1/properties"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, CurrentLandlord, require_unit_quota
from app.schemas.schemas import (
    PropertyCreate, PropertyResponse, PropertyUpdate,
    UnitCreate, UnitResponse, UnitUpdate,
)
from app.services.property_service import property_service

router = APIRouter(prefix="/properties", tags=["Properties"])


# ── Properties ────────────────────────────────────────────────────────────────

@router.get("", response_model=list[PropertyResponse])
async def list_properties(
    skip: int = 0, limit: int = 50,
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    props = await property_service.list_properties(db, landlord.id, skip, limit)
    result = []
    for p in props:
        d = PropertyResponse.model_validate(p)
        d.unit_count = len(p.units)
        result.append(d)
    return result


@router.post("", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_property(
    data: PropertyCreate,
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    prop = await property_service.create_property(db, landlord.id, data)
    await db.commit()
    return prop


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: UUID,
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    prop = await property_service.get_property(db, landlord.id, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found.")
    return prop


@router.patch("/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: UUID,
    data: PropertyUpdate,
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    prop = await property_service.get_property(db, landlord.id, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found.")
    return await property_service.update_property(db, prop, data)


# ── Units ─────────────────────────────────────────────────────────────────────

@router.get("/{property_id}/units", response_model=list[UnitResponse])
async def list_units(
    property_id: UUID,
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    return await property_service.list_units(db, landlord.id, property_id)


@router.post(
    "/{property_id}/units",
    response_model=UnitResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_unit_quota())],
)
async def create_unit(
    property_id: UUID,
    data: UnitCreate,
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    # Ensure property belongs to landlord
    prop = await property_service.get_property(db, landlord.id, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found.")
    data.property_id = property_id
    unit = await property_service.create_unit(db, landlord.id, data)
    await db.commit()
    return unit


@router.patch("/units/{unit_id}", response_model=UnitResponse)
async def update_unit(
    unit_id: UUID,
    data: UnitUpdate,
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    unit = await property_service.get_unit(db, landlord.id, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found.")
    updated = await property_service.update_unit(db, unit, data)
    await db.commit()
    return updated
