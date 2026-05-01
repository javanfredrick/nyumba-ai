"""
M-Pesa Router — /api/v1/mpesa
Handles Safaricom Daraja C2B callbacks strictly.
Multi-tenant routing via {landlord_id} path parameter.

SECURITY: Validation endpoint rejects any payment that cannot be
pre-validated, preventing manual "Black Book" entries from ever
reaching the database as COMPLETED.
"""
import structlog
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, CurrentLandlord
from app.core.config import settings
from app.schemas.schemas import MpesaCallbackBody, MpesaValidationResponse
from app.services.mpesa_service import mpesa_service
from app.services.payment_service import payment_service
from app.services.property_service import property_service
from app.services.landlord_service import landlord_service
from app.ai.agents.reconciliation_agent import run_reconciliation
from app.ai.chains.rag_chain import seed_vector_store
from app.models.landlord import FlagReason

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/mpesa", tags=["M-Pesa"])

# Safaricom expects these exact strings
RESULT_SUCCESS = MpesaValidationResponse(ResultCode="0", ResultDesc="Accepted")
RESULT_REJECT = MpesaValidationResponse(ResultCode="C2B00011", ResultDesc="Rejected")


# ── Register C2B URLs (landlord-initiated, one-time per go-live) ──────────────

@router.post("/register/{landlord_id}")
async def register_c2b(
    landlord_id: UUID = Path(...),
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Landlord triggers this once to register their callback URLs with Safaricom."""
    if landlord.id != landlord_id:
        raise HTTPException(status_code=403, detail="Cannot register for another landlord.")
    result = await mpesa_service.register_c2b_urls(str(landlord_id), landlord.mpesa_shortcode)
    return {"message": "C2B URLs registered", "safaricom_response": result}


# ── Validation Endpoint (called by Safaricom BEFORE debiting customer) ────────

@router.post(
    "/callback/{landlord_id}/validation",
    response_model=MpesaValidationResponse,
    include_in_schema=False,   # Don't expose in public API docs
)
async def c2b_validation(
    request: Request,
    landlord_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Safaricom calls this URL BEFORE processing the payment.
    We validate the BillRefNumber matches a known unit for this landlord.
    Returning ResultCode "0" → Proceed. Any other code → Reject.

    This is the ANTI-BLACK-BOOK gate: only payments with a valid
    account number for a real unit pass through.
    """
    try:
        body = await request.json()
        bill_ref = body.get("BillRefNumber", "").strip().upper()
        msisdn = body.get("MSISDN", "")
        amount = body.get("TransAmount", "0")
    except Exception:
        log.error("mpesa.validation_parse_error", landlord_id=str(landlord_id))
        return RESULT_REJECT

    log.info(
        "mpesa.validation_request",
        landlord_id=str(landlord_id),
        bill_ref=bill_ref,
        msisdn=msisdn,
        amount=amount,
    )

    # Verify landlord exists
    landlord = await landlord_service.get_by_id(db, landlord_id)
    if not landlord or not landlord.is_active:
        log.warning("mpesa.validation_unknown_landlord", landlord_id=str(landlord_id))
        return RESULT_REJECT

    # Strict check: BillRefNumber MUST match a real unit
    unit = await property_service.get_unit_by_account(db, landlord_id, bill_ref)
    if not unit:
        log.warning(
            "mpesa.validation_rejected_unknown_account",
            landlord_id=str(landlord_id),
            bill_ref=bill_ref,
        )
        return RESULT_REJECT

    log.info("mpesa.validation_accepted", landlord_id=str(landlord_id), unit_id=str(unit.id))
    return RESULT_SUCCESS


# ── Confirmation Endpoint (called AFTER M-Pesa debits the customer) ───────────

@router.post(
    "/callback/{landlord_id}/confirmation",
    include_in_schema=False,
)
async def c2b_confirmation(
    request: Request,
    landlord_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Safaricom calls this after the transaction is complete.
    We persist the payment and trigger the AI reconciliation agent.
    Always returns 200 (Safaricom retries on non-200).
    """
    try:
        raw_body = await request.json()
        body = MpesaCallbackBody(**raw_body)
    except Exception as e:
        log.error("mpesa.confirmation_parse_error", error=str(e))
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    log.info(
        "mpesa.confirmation_received",
        landlord_id=str(landlord_id),
        receipt=body.TransID,
        amount=body.TransAmount,
        msisdn=body.MSISDN,
    )

    # Persist raw payment (idempotent)
    payment = await payment_service.create_from_callback(db, landlord_id, body, raw_body)
    await db.commit()

    # Run AI reconciliation agent asynchronously
    try:
        payer_name = " ".join(filter(None, [body.FirstName, body.MiddleName, body.LastName]))
        final_state = await run_reconciliation(
            db=db,
            landlord_id=str(landlord_id),
            payment_id=str(payment.id),
            bill_ref_number=body.BillRefNumber,
            msisdn=body.MSISDN,
            amount=body.TransAmount,
            payer_name=payer_name,
        )

        # Fetch matched entities
        unit = None
        tenant = None
        if final_state.get("matched_unit_id"):
            unit = await property_service.get_unit(db, landlord_id, UUID(final_state["matched_unit_id"]))
        if final_state.get("matched_tenant_id"):
            from sqlalchemy import select
            from app.models.landlord import Tenant
            result = await db.execute(
                select(Tenant).where(Tenant.id == UUID(final_state["matched_tenant_id"]))
            )
            tenant = result.scalar_one_or_none()

        flagged = final_state["decision"] == "flag"
        flag_reason = FlagReason(final_state["flag_reason"]) if final_state.get("flag_reason") else None

        await payment_service.reconcile(
            db=db,
            payment=payment,
            unit=unit,
            tenant=tenant,
            notes=final_state["notes"],
            flagged=flagged,
            flag_reason=flag_reason,
            ai_explanation=final_state.get("ai_explanation"),
        )
        await db.commit()

        # Refresh RAG vector store in background
        await seed_vector_store(db, str(landlord_id))

    except Exception as e:
        log.error("mpesa.reconciliation_error", error=str(e), receipt=body.TransID)
        # Don't crash — payment is already saved as PENDING

    # Safaricom always needs a 200
    return {"ResultCode": 0, "ResultDesc": "Accepted"}


# ── STK Push (landlord-initiated payment request) ─────────────────────────────

@router.post("/stk-push")
async def stk_push(
    phone: str,
    amount: int,
    account_reference: str,
    landlord: CurrentLandlord = Depends(),
):
    """Send an STK Push prompt to a tenant's phone."""
    result = await mpesa_service.stk_push(
        phone=phone,
        amount=amount,
        account_reference=account_reference,
        transaction_desc=f"Rent payment - {account_reference}",
        landlord_id=str(landlord.id),
    )
    return result


# ── Payments list ─────────────────────────────────────────────────────────────

@router.get("/payments")
async def list_payments(
    status: str = None,
    skip: int = 0,
    limit: int = 50,
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    payments = await payment_service.list_payments(db, landlord.id, status, skip, limit)
    return payments


# ── Flagged payments ──────────────────────────────────────────────────────────

@router.get("/flags")
async def list_flags(
    resolved: bool = False,
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    return await payment_service.list_flags(db, landlord.id, resolved)


@router.post("/flags/{flag_id}/resolve")
async def resolve_flag(
    flag_id: UUID,
    data: dict,
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    from app.schemas.schemas import ResolveFlagRequest
    flag = await payment_service.get_flag(db, landlord.id, flag_id)
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found.")
    req = ResolveFlagRequest(**data)
    updated = await payment_service.resolve_flag(db, flag, landlord.email, req)
    await db.commit()
    return updated
