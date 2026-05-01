"""
Payment Service.
Handles saving raw M-Pesa callbacks, coordinating reconciliation,
flagging unmatched payments, and querying payment history.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.landlord import Payment, PaymentFlag, PaymentStatus, FlagReason, Tenant, Unit
from app.schemas.schemas import MpesaCallbackBody, ResolveFlagRequest

log = structlog.get_logger(__name__)


class PaymentService:

    # ── Ingest raw M-Pesa callback ────────────────────────────────────────────

    async def create_from_callback(
        self,
        db: AsyncSession,
        landlord_id: UUID,
        body: MpesaCallbackBody,
        raw: dict,
    ) -> Payment:
        """
        Persist the raw M-Pesa callback as a PENDING payment.
        Duplicate receipt numbers are silently ignored (idempotent).
        """
        # Idempotency guard
        existing = await self._get_by_receipt(db, body.TransID)
        if existing:
            log.info("payment.duplicate_ignored", receipt=body.TransID)
            return existing

        payment = Payment(
            landlord_id=landlord_id,
            mpesa_receipt_number=body.TransID,
            transaction_date=self._parse_ts(body.TransTime),
            amount=Decimal(body.TransAmount),
            msisdn=body.MSISDN,
            bill_ref_number=body.BillRefNumber.strip().upper(),
            first_name=body.FirstName,
            middle_name=body.MiddleName,
            last_name=body.LastName,
            organization_account_balance=(
                Decimal(body.OrgAccountBalance) if body.OrgAccountBalance else None
            ),
            status=PaymentStatus.PENDING,
            raw_callback=raw,
        )
        db.add(payment)
        await db.flush()
        log.info("payment.created", payment_id=str(payment.id), receipt=body.TransID)
        return payment

    # ── Match / Reconcile ─────────────────────────────────────────────────────

    async def reconcile(
        self,
        db: AsyncSession,
        payment: Payment,
        unit: Optional[Unit],
        tenant: Optional[Tenant],
        notes: str,
        flagged: bool = False,
        flag_reason: Optional[FlagReason] = None,
        ai_explanation: Optional[str] = None,
    ) -> Payment:
        """Apply reconciliation result to a payment record."""
        payment.unit_id = unit.id if unit else None
        payment.tenant_id = tenant.id if tenant else None
        payment.reconciliation_notes = notes
        payment.reconciled_at = datetime.now(timezone.utc)
        payment.status = PaymentStatus.FLAGGED if flagged else PaymentStatus.COMPLETED

        if flagged and flag_reason:
            flag = PaymentFlag(
                landlord_id=payment.landlord_id,
                payment_id=payment.id,
                reason=flag_reason,
                ai_explanation=ai_explanation,
            )
            db.add(flag)
            log.warning(
                "payment.flagged",
                payment_id=str(payment.id),
                reason=flag_reason,
            )

        if unit and not flagged:
            unit.is_occupied = True

        await db.flush()
        return payment

    # ── Resolve a flagged payment ─────────────────────────────────────────────

    async def resolve_flag(
        self,
        db: AsyncSession,
        flag: PaymentFlag,
        landlord_email: str,
        data: ResolveFlagRequest,
    ) -> PaymentFlag:
        flag.resolved = True
        flag.resolved_at = datetime.now(timezone.utc)
        flag.resolved_by = landlord_email
        flag.resolution_notes = data.resolution_notes

        payment = flag.payment
        if data.unit_id:
            payment.unit_id = data.unit_id
        if data.tenant_id:
            payment.tenant_id = data.tenant_id
        payment.status = PaymentStatus.COMPLETED

        await db.flush()
        return flag

    # ── Queries ───────────────────────────────────────────────────────────────

    async def list_payments(
        self,
        db: AsyncSession,
        landlord_id: UUID,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Payment]:
        q = (
            select(Payment)
            .where(Payment.landlord_id == landlord_id)
            .options(selectinload(Payment.flags))
            .order_by(Payment.transaction_date.desc())
            .offset(skip)
            .limit(limit)
        )
        if status:
            q = q.where(Payment.status == status)
        result = await db.execute(q)
        return list(result.scalars().all())

    async def list_flags(
        self, db: AsyncSession, landlord_id: UUID, resolved: bool = False
    ) -> List[PaymentFlag]:
        result = await db.execute(
            select(PaymentFlag)
            .where(
                PaymentFlag.landlord_id == landlord_id,
                PaymentFlag.resolved == resolved,
            )
            .options(selectinload(PaymentFlag.payment))
            .order_by(PaymentFlag.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_flag(
        self, db: AsyncSession, landlord_id: UUID, flag_id: UUID
    ) -> Optional[PaymentFlag]:
        result = await db.execute(
            select(PaymentFlag)
            .where(PaymentFlag.id == flag_id, PaymentFlag.landlord_id == landlord_id)
            .options(selectinload(PaymentFlag.payment))
        )
        return result.scalar_one_or_none()

    async def monthly_collected(self, db: AsyncSession, landlord_id: UUID) -> Decimal:
        from datetime import date
        today = date.today()
        result = await db.execute(
            select(func.sum(Payment.amount)).where(
                Payment.landlord_id == landlord_id,
                Payment.status == PaymentStatus.COMPLETED,
                func.date_trunc("month", Payment.transaction_date)
                == func.date_trunc("month", func.now()),
            )
        )
        return result.scalar_one() or Decimal("0")

    async def pending_flags_count(self, db: AsyncSession, landlord_id: UUID) -> int:
        result = await db.execute(
            select(func.count(PaymentFlag.id)).where(
                PaymentFlag.landlord_id == landlord_id,
                PaymentFlag.resolved == False,
            )
        )
        return result.scalar_one()

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _get_by_receipt(self, db: AsyncSession, receipt: str) -> Optional[Payment]:
        result = await db.execute(
            select(Payment).where(Payment.mpesa_receipt_number == receipt)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _parse_ts(ts: str) -> datetime:
        return datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


payment_service = PaymentService()
