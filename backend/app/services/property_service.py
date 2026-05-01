"""Property and Unit CRUD service."""
from typing import Optional, List
from uuid import UUID
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.landlord import Property, Unit
from app.schemas.schemas import PropertyCreate, PropertyUpdate, UnitCreate, UnitUpdate


class PropertyService:

    async def list_properties(
        self, db: AsyncSession, landlord_id: UUID, skip: int = 0, limit: int = 50
    ) -> List[Property]:
        result = await db.execute(
            select(Property)
            .where(Property.landlord_id == landlord_id, Property.is_active == True)
            .options(selectinload(Property.units))
            .offset(skip)
            .limit(limit)
            .order_by(Property.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_property(
        self, db: AsyncSession, landlord_id: UUID, property_id: UUID
    ) -> Optional[Property]:
        result = await db.execute(
            select(Property).where(
                Property.id == property_id,
                Property.landlord_id == landlord_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_property(
        self, db: AsyncSession, landlord_id: UUID, data: PropertyCreate
    ) -> Property:
        prop = Property(landlord_id=landlord_id, **data.model_dump())
        db.add(prop)
        await db.flush()
        return prop

    async def update_property(
        self, db: AsyncSession, prop: Property, data: PropertyUpdate
    ) -> Property:
        for k, v in data.model_dump(exclude_none=True).items():
            setattr(prop, k, v)
        await db.flush()
        return prop

    async def count_units(self, db: AsyncSession, landlord_id: UUID) -> int:
        result = await db.execute(
            select(func.count(Unit.id)).where(Unit.landlord_id == landlord_id)
        )
        return result.scalar_one()

    # ── Unit ──────────────────────────────────────────────────────────────────

    async def list_units(
        self, db: AsyncSession, landlord_id: UUID, property_id: Optional[UUID] = None
    ) -> List[Unit]:
        q = select(Unit).where(Unit.landlord_id == landlord_id)
        if property_id:
            q = q.where(Unit.property_id == property_id)
        result = await db.execute(q.order_by(Unit.unit_number))
        return list(result.scalars().all())

    async def get_unit(
        self, db: AsyncSession, landlord_id: UUID, unit_id: UUID
    ) -> Optional[Unit]:
        result = await db.execute(
            select(Unit).where(Unit.id == unit_id, Unit.landlord_id == landlord_id)
        )
        return result.scalar_one_or_none()

    async def get_unit_by_account(
        self, db: AsyncSession, landlord_id: UUID, account_number: str
    ) -> Optional[Unit]:
        """Used by M-Pesa reconciliation to match BillRefNumber → Unit."""
        result = await db.execute(
            select(Unit).where(
                Unit.landlord_id == landlord_id,
                Unit.account_number == account_number.strip().upper(),
            )
        )
        return result.scalar_one_or_none()

    async def create_unit(
        self, db: AsyncSession, landlord_id: UUID, data: UnitCreate
    ) -> Unit:
        unit = Unit(
            landlord_id=landlord_id,
            **data.model_dump(),
        )
        db.add(unit)
        await db.flush()
        return unit

    async def update_unit(self, db: AsyncSession, unit: Unit, data: UnitUpdate) -> Unit:
        for k, v in data.model_dump(exclude_none=True).items():
            setattr(unit, k, v)
        await db.flush()
        return unit

    async def get_dashboard_stats(self, db: AsyncSession, landlord_id: UUID) -> dict:
        prop_count = await db.execute(
            select(func.count(Property.id)).where(
                Property.landlord_id == landlord_id, Property.is_active == True
            )
        )
        unit_count = await db.execute(
            select(func.count(Unit.id)).where(Unit.landlord_id == landlord_id)
        )
        occupied = await db.execute(
            select(func.count(Unit.id)).where(
                Unit.landlord_id == landlord_id, Unit.is_occupied == True
            )
        )
        expected_revenue = await db.execute(
            select(func.sum(Unit.monthly_rent)).where(
                Unit.landlord_id == landlord_id, Unit.is_occupied == True
            )
        )
        return {
            "total_properties": prop_count.scalar_one(),
            "total_units": unit_count.scalar_one(),
            "occupied_units": occupied.scalar_one(),
            "monthly_expected_revenue": expected_revenue.scalar_one() or Decimal("0"),
        }


property_service = PropertyService()
