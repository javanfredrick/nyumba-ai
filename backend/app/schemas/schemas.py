"""
Pydantic v2 schemas — request bodies, response models, and internal DTOs.
Organized by domain. All sensitive fields are write-only (exclude from responses).
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Any
from uuid import UUID
import enum

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator


# ── Shared ────────────────────────────────────────────────────────────────────

class OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Auth ──────────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    refresh_token: str


class GoogleCallbackRequest(BaseModel):
    code: str
    state: Optional[str] = None


# ── Landlord ──────────────────────────────────────────────────────────────────

class LandlordRegister(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    phone: Optional[str] = Field(None, pattern=r"^(\+254|0|254)[17]\d{8}$")
    password: str = Field(min_length=8)


class LandlordLogin(BaseModel):
    email: EmailStr
    password: str


class LandlordResponse(OrmBase):
    id: UUID
    email: str
    full_name: str
    phone: Optional[str]
    avatar_url: Optional[str]
    subscription_tier: str
    ai_tokens_used: int
    ai_tokens_limit: int
    is_verified: bool
    created_at: datetime


class LandlordUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    mpesa_shortcode: Optional[str] = None


# ── Property ──────────────────────────────────────────────────────────────────

class PropertyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    address: str
    city: str = "Nairobi"
    county: str = "Nairobi"
    description: Optional[str] = None
    image_url: Optional[str] = None


class PropertyResponse(OrmBase):
    id: UUID
    landlord_id: UUID
    name: str
    address: str
    city: str
    county: str
    description: Optional[str]
    image_url: Optional[str]
    is_active: bool
    created_at: datetime
    unit_count: Optional[int] = 0


class PropertyUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None


# ── Unit ──────────────────────────────────────────────────────────────────────

class UnitCreate(BaseModel):
    property_id: UUID
    account_number: str = Field(min_length=3, max_length=20)
    unit_number: str = Field(min_length=1, max_length=50)
    floor: Optional[int] = None
    bedrooms: int = Field(default=1, ge=0)
    bathrooms: int = Field(default=1, ge=0)
    monthly_rent: Decimal = Field(gt=0)
    deposit_amount: Decimal = Field(default=0, ge=0)


class UnitResponse(OrmBase):
    id: UUID
    landlord_id: UUID
    property_id: UUID
    account_number: str
    unit_number: str
    floor: Optional[int]
    bedrooms: int
    bathrooms: int
    is_occupied: bool
    monthly_rent: Decimal
    deposit_amount: Decimal
    created_at: datetime


class UnitUpdate(BaseModel):
    monthly_rent: Optional[Decimal] = None
    deposit_amount: Optional[Decimal] = None
    is_occupied: Optional[bool] = None


# ── Tenant ────────────────────────────────────────────────────────────────────

class TenantCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: Optional[EmailStr] = None
    phone: str = Field(pattern=r"^(2547|2541)\d{8}$")   # MSISDN format
    national_id: Optional[str] = None


class TenantResponse(OrmBase):
    id: UUID
    landlord_id: UUID
    full_name: str
    email: Optional[str]
    phone: str
    national_id: Optional[str]
    is_active: bool
    created_at: datetime


# ── Lease ─────────────────────────────────────────────────────────────────────

class LeaseCreate(BaseModel):
    unit_id: UUID
    tenant_id: UUID
    lease_type: str = Field(pattern=r"^(rent|mortgage)$")
    start_date: date
    end_date: Optional[date] = None
    monthly_amount: Decimal = Field(gt=0)
    deposit_paid: Decimal = Field(default=0, ge=0)
    notes: Optional[str] = None


class LeaseResponse(OrmBase):
    id: UUID
    landlord_id: UUID
    unit_id: UUID
    tenant_id: Optional[UUID]
    lease_type: str
    start_date: date
    end_date: Optional[date]
    monthly_amount: Decimal
    deposit_paid: Decimal
    is_active: bool
    created_at: datetime


# ── Mortgage ──────────────────────────────────────────────────────────────────

class MortgageCreate(BaseModel):
    lease_id: UUID
    principal_amount: Decimal = Field(gt=0)
    interest_rate: Decimal = Field(gt=0, lt=1)   # 0.135 = 13.5%
    tenure_months: int = Field(gt=0)
    disbursement_date: date


class MortgageResponse(OrmBase):
    id: UUID
    landlord_id: UUID
    lease_id: UUID
    principal_amount: Decimal
    interest_rate: Decimal
    tenure_months: int
    outstanding_balance: Decimal
    monthly_installment: Decimal
    status: str
    disbursement_date: date
    amortization_schedule: Optional[Any]
    created_at: datetime


# ── Payment / M-Pesa ──────────────────────────────────────────────────────────

class MpesaCallbackBody(BaseModel):
    """Raw M-Pesa C2B Callback payload from Safaricom Daraja."""
    TransactionType: str
    TransID: str
    TransTime: str
    TransAmount: str
    BusinessShortCode: str
    BillRefNumber: str
    InvoiceNumber: Optional[str] = None
    OrgAccountBalance: Optional[str] = None
    ThirdPartyTransID: Optional[str] = None
    MSISDN: str
    FirstName: Optional[str] = None
    MiddleName: Optional[str] = None
    LastName: Optional[str] = None


class MpesaValidationResponse(BaseModel):
    """Safaricom expects this exact structure for validation."""
    ResultCode: str
    ResultDesc: str


class PaymentResponse(OrmBase):
    id: UUID
    landlord_id: UUID
    unit_id: Optional[UUID]
    tenant_id: Optional[UUID]
    mpesa_receipt_number: str
    transaction_date: datetime
    amount: Decimal
    msisdn: str
    bill_ref_number: str
    first_name: Optional[str]
    last_name: Optional[str]
    status: str
    reconciled_at: Optional[datetime]
    reconciliation_notes: Optional[str]
    created_at: datetime


class PaymentFlagResponse(OrmBase):
    id: UUID
    payment_id: UUID
    reason: str
    ai_explanation: Optional[str]
    resolved: bool
    resolved_at: Optional[datetime]
    resolution_notes: Optional[str]
    created_at: datetime


class ResolveFlagRequest(BaseModel):
    unit_id: Optional[UUID] = None
    tenant_id: Optional[UUID] = None
    resolution_notes: str


# ── AI / RAG ──────────────────────────────────────────────────────────────────

class AIQueryRequest(BaseModel):
    question: str = Field(min_length=5, max_length=1000)


class AIQueryResponse(BaseModel):
    answer: str
    sources: List[str] = []
    tokens_used: int
    cost_kes: float


# ── Dashboard ─────────────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_properties: int
    total_units: int
    occupied_units: int
    vacant_units: int
    total_tenants: int
    monthly_expected_revenue: Decimal
    monthly_collected_revenue: Decimal
    collection_rate: float
    pending_flags: int
    ai_tokens_used: int
    ai_tokens_limit: int


# ── Pagination ────────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    size: int
    pages: int
