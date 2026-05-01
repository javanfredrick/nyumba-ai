"""Landlord CRUD service — all DB operations for Landlord entities."""
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.landlord import Landlord
from app.schemas.schemas import LandlordRegister, LandlordUpdate
from app.core.security import hash_password


class LandlordService:

    async def get_by_id(self, db: AsyncSession, landlord_id: UUID) -> Optional[Landlord]:
        result = await db.execute(select(Landlord).where(Landlord.id == landlord_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[Landlord]:
        result = await db.execute(select(Landlord).where(Landlord.email == email.lower()))
        return result.scalar_one_or_none()

    async def get_by_google_sub(self, db: AsyncSession, sub: str) -> Optional[Landlord]:
        result = await db.execute(select(Landlord).where(Landlord.google_sub == sub))
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, data: LandlordRegister) -> Landlord:
        landlord = Landlord(
            email=data.email.lower(),
            full_name=data.full_name,
            phone=data.phone,
            hashed_password=hash_password(data.password),
            is_verified=False,
        )
        db.add(landlord)
        await db.flush()
        return landlord

    async def create_from_google(
        self, db: AsyncSession, sub: str, email: str, name: str, avatar: Optional[str]
    ) -> Landlord:
        landlord = Landlord(
            email=email.lower(),
            full_name=name,
            google_sub=sub,
            avatar_url=avatar,
            is_verified=True,  # Google email already verified
        )
        db.add(landlord)
        await db.flush()
        return landlord

    async def update(self, db: AsyncSession, landlord: Landlord, data: LandlordUpdate) -> Landlord:
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(landlord, field, value)
        await db.flush()
        return landlord

    async def increment_ai_tokens(self, db: AsyncSession, landlord_id: UUID, tokens: int) -> None:
        landlord = await self.get_by_id(db, landlord_id)
        if landlord:
            landlord.ai_tokens_used += tokens
            await db.flush()


landlord_service = LandlordService()
