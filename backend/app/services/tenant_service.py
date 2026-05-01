"""Tenant and Lease CRUD service."""
from typing import Optional, List
from uuid import UUID
from decimal import Decimal
import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.landlord import Tenant, Lease, MortgageAccount, MortgageStatus, LeaseType
from app.schemas.schemas import TenantCreate, LeaseCreate, MortgageCreate


class TenantService:

    async def list_tenants(
        self, db: AsyncSession, landlord_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Tenant]:
        result = await db.execute(
            select(Tenant)
            .where(Tenant.landlord_id == landlord_id, Tenant.is_active == True)
            .order_by(Tenant.full_name)
            .offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def get_tenant(
        self, db: AsyncSession, landlord_id: UUID, tenant_id: UUID
    ) -> Optional[Tenant]:
        result = await db.execute(
            select(Tenant).where(
                Tenant.id == tenant_id, Tenant.landlord_id == landlord_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_phone(
        self, db: AsyncSession, landlord_id: UUID, phone: str
    ) -> Optional[Tenant]:
        result = await db.execute(
            select(Tenant).where(
                Tenant.landlord_id == landlord_id, Tenant.phone == phone
            )
        )
        return result.scalar_one_or_none()

    async def create_tenant(
        self, db: AsyncSession, landlord_id: UUID, data: TenantCreate
    ) -> Tenant:
        tenant = Tenant(landlord_id=landlord_id, **data.model_dump())
        db.add(tenant)
        await db.flush()
        return tenant

    async def update_tenant(
        self, db: AsyncSession, tenant: Tenant, data: dict
    ) -> Tenant:
        for k, v in data.items():
            if v is not None:
                setattr(tenant, k, v)
        await db.flush()
        return tenant

    async def deactivate_tenant(self, db: AsyncSession, tenant: Tenant) -> Tenant:
        tenant.is_active = False
        await db.flush()
        return tenant


class LeaseService:

    async def list_leases(
        self, db: AsyncSession, landlord_id: UUID, active_only: bool = True
    ) -> List[Lease]:
        q = select(Lease).where(Lease.landlord_id == landlord_id)
        if active_only:
            q = q.where(Lease.is_active == True)
        q = q.options(
            selectinload(Lease.unit),
            selectinload(Lease.tenant),
            selectinload(Lease.mortgage),
        ).order_by(Lease.created_at.desc())
        result = await db.execute(q)
        return list(result.scalars().all())

    async def get_lease(
        self, db: AsyncSession, landlord_id: UUID, lease_id: UUID
    ) -> Optional[Lease]:
        result = await db.execute(
            select(Lease)
            .where(Lease.id == lease_id, Lease.landlord_id == landlord_id)
            .options(selectinload(Lease.unit), selectinload(Lease.tenant), selectinload(Lease.mortgage))
        )
        return result.scalar_one_or_none()

    async def create_lease(
        self, db: AsyncSession, landlord_id: UUID, data: LeaseCreate
    ) -> Lease:
        lease = Lease(landlord_id=landlord_id, **data.model_dump())
        db.add(lease)

        # Mark unit as occupied
        from app.services.property_service import property_service
        unit = await property_service.get_unit(db, landlord_id, data.unit_id)
        if unit:
            unit.is_occupied = True

        await db.flush()
        return lease

    async def terminate_lease(self, db: AsyncSession, lease: Lease) -> Lease:
        lease.is_active = False
        if lease.unit:
            lease.unit.is_occupied = False
        await db.flush()
        return lease


class MortgageService:
    """
    Handles mortgage creation with automatic amortization schedule calculation.
    Uses the standard reducing balance (French amortization) method.
    """

    def _calculate_monthly_installment(
        self, principal: Decimal, annual_rate: Decimal, months: int
    ) -> Decimal:
        """M = P * [r(1+r)^n] / [(1+r)^n - 1]"""
        r = annual_rate / Decimal("12")
        n = months
        if r == 0:
            return principal / Decimal(n)
        factor = (1 + float(r)) ** n
        monthly = float(principal) * (float(r) * factor) / (factor - 1)
        return Decimal(str(round(monthly, 2)))

    def _build_amortization_schedule(
        self,
        principal: Decimal,
        annual_rate: Decimal,
        months: int,
        monthly_installment: Decimal,
    ) -> list[dict]:
        """Generate full amortization table."""
        schedule = []
        balance = principal
        monthly_rate = annual_rate / Decimal("12")

        for period in range(1, months + 1):
            interest = (balance * monthly_rate).quantize(Decimal("0.01"))
            principal_payment = (monthly_installment - interest).quantize(Decimal("0.01"))
            balance = max(Decimal("0"), (balance - principal_payment).quantize(Decimal("0.01")))
            schedule.append({
                "period": period,
                "installment": float(monthly_installment),
                "principal": float(principal_payment),
                "interest": float(interest),
                "balance": float(balance),
            })
        return schedule

    async def create_mortgage(
        self, db: AsyncSession, landlord_id: UUID, data: MortgageCreate
    ) -> MortgageAccount:
        monthly = self._calculate_monthly_installment(
            data.principal_amount, data.interest_rate, data.tenure_months
        )
        schedule = self._build_amortization_schedule(
            data.principal_amount, data.interest_rate, data.tenure_months, monthly
        )
        mortgage = MortgageAccount(
            landlord_id=landlord_id,
            lease_id=data.lease_id,
            principal_amount=data.principal_amount,
            interest_rate=data.interest_rate,
            tenure_months=data.tenure_months,
            outstanding_balance=data.principal_amount,
            monthly_installment=monthly,
            disbursement_date=data.disbursement_date,
            amortization_schedule=schedule,
        )
        db.add(mortgage)
        await db.flush()
        return mortgage

    async def apply_payment(
        self, db: AsyncSession, mortgage: MortgageAccount, amount: Decimal
    ) -> MortgageAccount:
        """Reduce outstanding balance by the principal portion of a payment."""
        monthly_rate = mortgage.interest_rate / Decimal("12")
        interest_due = (mortgage.outstanding_balance * monthly_rate).quantize(Decimal("0.01"))
        principal_paid = max(Decimal("0"), amount - interest_due)
        mortgage.outstanding_balance = max(
            Decimal("0"),
            (mortgage.outstanding_balance - principal_paid).quantize(Decimal("0.01"))
        )
        if mortgage.outstanding_balance == Decimal("0"):
            mortgage.status = MortgageStatus.COMPLETED
        await db.flush()
        return mortgage

    async def get_mortgage(
        self, db: AsyncSession, landlord_id: UUID, mortgage_id: UUID
    ) -> Optional[MortgageAccount]:
        result = await db.execute(
            select(MortgageAccount).where(
                MortgageAccount.id == mortgage_id,
                MortgageAccount.landlord_id == landlord_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_mortgages(
        self, db: AsyncSession, landlord_id: UUID
    ) -> List[MortgageAccount]:
        result = await db.execute(
            select(MortgageAccount)
            .where(MortgageAccount.landlord_id == landlord_id)
            .order_by(MortgageAccount.created_at.desc())
        )
        return list(result.scalars().all())


tenant_service = TenantService()
lease_service = LeaseService()
mortgage_service = MortgageService()
