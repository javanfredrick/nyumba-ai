"""
ORM Models — single file for clarity; each class maps to a DB table.
All multi-tenant tables carry landlord_id (FK + RLS anchor).
"""
import enum
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, ForeignKey, Integer,
    Numeric, String, Text, BigInteger, func, UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.session import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class SubscriptionTier(str, enum.Enum):
    STARTER = "starter"       # ≤ 10 units
    GROWTH = "growth"         # ≤ 50 units
    ENTERPRISE = "enterprise" # Unlimited


class LeaseType(str, enum.Enum):
    RENT = "rent"
    MORTGAGE = "mortgage"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FLAGGED = "flagged"
    REFUNDED = "refunded"


class FlagReason(str, enum.Enum):
    UNMATCHED_ACCOUNT = "unmatched_account"
    UNMATCHED_PHONE = "unmatched_phone"
    DUPLICATE = "duplicate"
    AMOUNT_MISMATCH = "amount_mismatch"
    MANUAL_ENTRY = "manual_entry"


class MortgageStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    DEFAULTED = "defaulted"


# ── Mixins ────────────────────────────────────────────────────────────────────

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


# ── Landlord (Top-level tenant) ───────────────────────────────────────────────

class Landlord(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "landlords"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255))  # None for OAuth
    google_sub: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Subscription
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        Enum(SubscriptionTier), default=SubscriptionTier.STARTER, nullable=False
    )
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(255))
    subscription_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # AI usage metering (tokens consumed this billing cycle)
    ai_tokens_used: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    ai_tokens_limit: Mapped[int] = mapped_column(BigInteger, default=100_000, nullable=False)

    # M-Pesa shortcode assigned to landlord (can override global)
    mpesa_shortcode: Mapped[Optional[str]] = mapped_column(String(20))

    # Relationships
    properties: Mapped[List["Property"]] = relationship(back_populates="landlord", cascade="all, delete-orphan")
    payments: Mapped[List["Payment"]] = relationship(back_populates="landlord", cascade="all, delete-orphan")
    ai_usage_logs: Mapped[List["AIUsageLog"]] = relationship(back_populates="landlord", cascade="all, delete-orphan")


# ── Property ──────────────────────────────────────────────────────────────────

class Property(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "properties"

    landlord_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("landlords.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(String(100), default="Nairobi")
    county: Mapped[str] = mapped_column(String(100), default="Nairobi")
    description: Mapped[Optional[str]] = mapped_column(Text)
    image_url: Mapped[Optional[str]] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    landlord: Mapped["Landlord"] = relationship(back_populates="properties")
    units: Mapped[List["Unit"]] = relationship(back_populates="property", cascade="all, delete-orphan")


# ── Unit ──────────────────────────────────────────────────────────────────────

class Unit(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "units"

    landlord_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("landlords.id", ondelete="CASCADE"), nullable=False, index=True
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False
    )
    # Account number tenants quote on M-Pesa (must be unique per landlord)
    account_number: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_number: Mapped[str] = mapped_column(String(50), nullable=False)
    floor: Mapped[Optional[int]] = mapped_column(Integer)
    bedrooms: Mapped[int] = mapped_column(Integer, default=1)
    bathrooms: Mapped[int] = mapped_column(Integer, default=1)
    is_occupied: Mapped[bool] = mapped_column(Boolean, default=False)
    monthly_rent: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    deposit_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    property: Mapped["Property"] = relationship(back_populates="units")
    leases: Mapped[List["Lease"]] = relationship(back_populates="unit", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("landlord_id", "account_number", name="uq_unit_account_per_landlord"),
        Index("ix_unit_account_landlord", "landlord_id", "account_number"),
    )


# ── Tenant ────────────────────────────────────────────────────────────────────

class Tenant(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    landlord_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("landlords.id", ondelete="CASCADE"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    # Phone stored as registered on M-Pesa (MSISDN format: 2547XXXXXXXX)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    national_id: Mapped[Optional[str]] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    leases: Mapped[List["Lease"]] = relationship(back_populates="tenant")


# ── Lease ─────────────────────────────────────────────────────────────────────

class Lease(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "leases"

    landlord_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("landlords.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True
    )
    lease_type: Mapped[LeaseType] = mapped_column(Enum(LeaseType), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    monthly_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    deposit_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    unit: Mapped["Unit"] = relationship(back_populates="leases")
    tenant: Mapped[Optional["Tenant"]] = relationship(back_populates="leases")
    mortgage: Mapped[Optional["MortgageAccount"]] = relationship(back_populates="lease", uselist=False)


# ── Mortgage Account (amortizing balance) ─────────────────────────────────────

class MortgageAccount(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "mortgage_accounts"

    landlord_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("landlords.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lease_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leases.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    principal_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)  # e.g. 0.1350 = 13.5%
    tenure_months: Mapped[int] = mapped_column(Integer, nullable=False)
    outstanding_balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    monthly_installment: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[MortgageStatus] = mapped_column(Enum(MortgageStatus), default=MortgageStatus.ACTIVE)
    disbursement_date: Mapped[date] = mapped_column(Date, nullable=False)
    amortization_schedule: Mapped[Optional[dict]] = mapped_column(JSONB)  # cached schedule

    lease: Mapped["Lease"] = relationship(back_populates="mortgage")


# ── Payment ───────────────────────────────────────────────────────────────────

class Payment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "payments"

    landlord_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("landlords.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unit_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units.id", ondelete="SET NULL"), nullable=True
    )
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True
    )

    # Raw M-Pesa payload fields
    mpesa_receipt_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    msisdn: Mapped[str] = mapped_column(String(20), nullable=False)        # Payer phone
    bill_ref_number: Mapped[str] = mapped_column(String(50), nullable=False)  # Account quoted
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    middle_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    organization_account_balance: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))

    # Reconciliation
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    reconciled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reconciliation_notes: Mapped[Optional[str]] = mapped_column(Text)
    raw_callback: Mapped[Optional[dict]] = mapped_column(JSONB)  # Full M-Pesa payload

    landlord: Mapped["Landlord"] = relationship(back_populates="payments")
    flags: Mapped[List["PaymentFlag"]] = relationship(back_populates="payment", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_payment_msisdn_landlord", "landlord_id", "msisdn"),)


# ── Payment Flag ──────────────────────────────────────────────────────────────

class PaymentFlag(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "payment_flags"

    landlord_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("landlords.id", ondelete="CASCADE"), nullable=False, index=True
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[FlagReason] = mapped_column(Enum(FlagReason), nullable=False)
    ai_explanation: Mapped[Optional[str]] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[Optional[str]] = mapped_column(String(255))
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text)

    payment: Mapped["Payment"] = relationship(back_populates="flags")


# ── AI Usage Log (token metering) ─────────────────────────────────────────────

class AIUsageLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ai_usage_logs"

    landlord_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("landlords.id", ondelete="CASCADE"), nullable=False, index=True
    )
    operation: Mapped[str] = mapped_column(String(100), nullable=False)   # e.g. "reconcile" | "rag_query"
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_kes: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    langsmith_run_id: Mapped[Optional[str]] = mapped_column(String(255))

    landlord: Mapped["Landlord"] = relationship(back_populates="ai_usage_logs")
