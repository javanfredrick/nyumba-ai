"""
Tenants, Leases & Mortgages Router — /api/v1/tenants
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, CurrentLandlord
from app.schemas.schemas import (
    TenantCreate, TenantResponse,
    LeaseCreate, LeaseResponse,
    MortgageCreate, MortgageResponse,
)
from app.services.tenant_service import tenant_service, lease_service, mortgage_service

router = APIRouter(prefix="/tenants", tags=["Tenants & Leases"])


# ── Tenants ───────────────────────────────────────────────────────────────────

@router.get("", response_model=list[TenantResponse])
async def list_tenants(
    skip: int = 0, limit: int = 100,
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    return await tenant_service.list_tenants(db, landlord.id, skip, limit)


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    data: TenantCreate,
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    # Prevent duplicate phone per landlord
    existing = await tenant_service.get_by_phone(db, landlord.id, data.phone)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"A tenant with phone {data.phone} already exists."
        )
    tenant = await tenant_service.create_tenant(db, landlord.id, data)
    await db.commit()
    return tenant


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: UUID,
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    tenant = await tenant_service.get_tenant(db, landlord.id, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    return tenant


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: UUID,
    data: dict,
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    tenant = await tenant_service.get_tenant(db, landlord.id, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    updated = await tenant_service.update_tenant(db, tenant, data)
    await db.commit()
    return updated


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_tenant(
    tenant_id: UUID,
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    tenant = await tenant_service.get_tenant(db, landlord.id, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    await tenant_service.deactivate_tenant(db, tenant)
    await db.commit()


# ── Leases ────────────────────────────────────────────────────────────────────

@router.get("/leases/all", response_model=list[LeaseResponse])
async def list_leases(
    active_only: bool = True,
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    return await lease_service.list_leases(db, landlord.id, active_only)


@router.post("/leases", response_model=LeaseResponse, status_code=status.HTTP_201_CREATED)
async def create_lease(
    data: LeaseCreate,
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    lease = await lease_service.create_lease(db, landlord.id, data)
    await db.commit()
    return lease


@router.get("/leases/{lease_id}", response_model=LeaseResponse)
async def get_lease(
    lease_id: UUID,
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    lease = await lease_service.get_lease(db, landlord.id, lease_id)
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found.")
    return lease


@router.post("/leases/{lease_id}/terminate", response_model=LeaseResponse)
async def terminate_lease(
    lease_id: UUID,
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    lease = await lease_service.get_lease(db, landlord.id, lease_id)
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found.")
    updated = await lease_service.terminate_lease(db, lease)
    await db.commit()
    return updated


# ── Mortgages ─────────────────────────────────────────────────────────────────

@router.get("/mortgages/all", response_model=list[MortgageResponse])
async def list_mortgages(
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    return await mortgage_service.list_mortgages(db, landlord.id)


@router.post("/mortgages", response_model=MortgageResponse, status_code=status.HTTP_201_CREATED)
async def create_mortgage(
    data: MortgageCreate,
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    # Ensure lease belongs to this landlord
    lease = await lease_service.get_lease(db, landlord.id, data.lease_id)
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found.")
    if lease.mortgage:
        raise HTTPException(status_code=400, detail="This lease already has a mortgage account.")

    mortgage = await mortgage_service.create_mortgage(db, landlord.id, data)
    await db.commit()
    return mortgage


@router.get("/mortgages/{mortgage_id}", response_model=MortgageResponse)
async def get_mortgage(
    mortgage_id: UUID,
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    mortgage = await mortgage_service.get_mortgage(db, landlord.id, mortgage_id)
    if not mortgage:
        raise HTTPException(status_code=404, detail="Mortgage not found.")
    return mortgage
