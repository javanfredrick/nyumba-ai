"""
LangGraph Reconciliation Agent.
Stateful graph that takes a raw M-Pesa payment and decides:
  1. Match by BillRefNumber (account number) → find unit
  2. Match by MSISDN (phone) → find tenant
  3. Cross-validate amount vs expected rent
  4. Either COMPLETE the payment or FLAG it with a reason + AI explanation

State flows: START → match_account → match_phone → validate_amount → decide → END
"""
from __future__ import annotations

import os
from typing import TypedDict, Optional, Annotated
from decimal import Decimal
from uuid import UUID

import structlog
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from app.core.config import settings
from app.models.landlord import FlagReason

log = structlog.get_logger(__name__)

# ── Set LangSmith env vars ────────────────────────────────────────────────────
os.environ["LANGCHAIN_TRACING_V2"] = str(settings.LANGCHAIN_TRACING_V2).lower()
os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT


# ── State Schema ──────────────────────────────────────────────────────────────

class ReconciliationState(TypedDict):
    # Inputs (set before graph runs)
    landlord_id: str
    payment_id: str
    bill_ref_number: str          # BillRefNumber from M-Pesa
    msisdn: str                   # Payer phone (MSISDN)
    amount: str                   # Payment amount as string (Decimal-safe)
    payer_name: str               # "FirstName MiddleName LastName"

    # Populated by nodes
    matched_unit_id: Optional[str]
    matched_unit_account: Optional[str]
    expected_rent: Optional[str]
    matched_tenant_id: Optional[str]
    matched_tenant_phone: Optional[str]

    # Decision output
    decision: Optional[str]       # "complete" | "flag"
    flag_reason: Optional[str]    # FlagReason value
    notes: str                    # Human-readable reconciliation notes
    ai_explanation: Optional[str] # LLM explanation for flags

    # Internal tool results
    messages: Annotated[list, add_messages]


# ── LLM ───────────────────────────────────────────────────────────────────────

def _get_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.1,
    )


# ── Node: Match by Account Number ─────────────────────────────────────────────

async def match_account_node(state: ReconciliationState, *, db) -> ReconciliationState:
    """Look up unit by BillRefNumber within the landlord's scope."""
    from app.services.property_service import property_service

    unit = await property_service.get_unit_by_account(
        db,
        landlord_id=UUID(state["landlord_id"]),
        account_number=state["bill_ref_number"],
    )

    if unit:
        log.info("reconcile.account_matched", unit_id=str(unit.id), account=state["bill_ref_number"])
        return {
            **state,
            "matched_unit_id": str(unit.id),
            "matched_unit_account": unit.account_number,
            "expected_rent": str(unit.monthly_rent),
        }

    log.warning("reconcile.account_not_matched", bill_ref=state["bill_ref_number"])
    return {**state, "matched_unit_id": None, "expected_rent": None}


# ── Node: Match by Phone (MSISDN) ─────────────────────────────────────────────

async def match_phone_node(state: ReconciliationState, *, db) -> ReconciliationState:
    """If account didn't match, try to find tenant by phone number."""
    from sqlalchemy import select
    from app.models.landlord import Tenant

    result = await db.execute(
        select(Tenant).where(
            Tenant.landlord_id == UUID(state["landlord_id"]),
            Tenant.phone == state["msisdn"],
            Tenant.is_active == True,
        )
    )
    tenant = result.scalar_one_or_none()

    if tenant:
        log.info("reconcile.phone_matched", tenant_id=str(tenant.id))
        return {
            **state,
            "matched_tenant_id": str(tenant.id),
            "matched_tenant_phone": tenant.phone,
        }

    log.warning("reconcile.phone_not_matched", msisdn=state["msisdn"])
    return {**state, "matched_tenant_id": None}


# ── Node: Validate Amount ─────────────────────────────────────────────────────

async def validate_amount_node(state: ReconciliationState) -> ReconciliationState:
    """Check if paid amount is within ±5% of expected rent."""
    if not state.get("expected_rent") or not state.get("matched_unit_id"):
        return state  # Nothing to validate against

    paid = Decimal(state["amount"])
    expected = Decimal(state["expected_rent"])
    tolerance = expected * Decimal("0.05")

    if abs(paid - expected) <= tolerance:
        return {**state, "amount_valid": True}
    return {**state, "amount_valid": False}


# ── Node: AI Decision ─────────────────────────────────────────────────────────

async def decide_node(state: ReconciliationState) -> ReconciliationState:
    """
    Use Gemini to synthesize all signals and produce a decision + explanation.
    """
    has_unit = bool(state.get("matched_unit_id"))
    has_tenant = bool(state.get("matched_tenant_id"))
    amount_ok = state.get("amount_valid", True)

    # Fast path — perfect match, no LLM needed
    if has_unit and has_tenant and amount_ok:
        return {
            **state,
            "decision": "complete",
            "flag_reason": None,
            "notes": (
                f"Payment matched: Unit {state['matched_unit_account']}, "
                f"Tenant {state['matched_tenant_phone']}. Amount verified."
            ),
            "ai_explanation": None,
        }

    # Determine flag reason
    if not has_unit and not has_tenant:
        flag_reason = FlagReason.UNMATCHED_ACCOUNT.value
    elif not has_unit:
        flag_reason = FlagReason.UNMATCHED_ACCOUNT.value
    elif not has_tenant:
        flag_reason = FlagReason.UNMATCHED_PHONE.value
    elif not amount_ok:
        flag_reason = FlagReason.AMOUNT_MISMATCH.value
    else:
        flag_reason = FlagReason.UNMATCHED_ACCOUNT.value

    # Ask LLM for a landlord-friendly explanation
    llm = _get_llm()
    prompt = f"""You are a payment reconciliation assistant for a Kenyan property management system.

A tenant payment came in via M-Pesa with these details:
- Account quoted (BillRefNumber): {state['bill_ref_number']}
- Payer phone (MSISDN): {state['msisdn']}
- Payer name: {state['payer_name']}
- Amount paid: KES {state['amount']}
- Expected rent: KES {state.get('expected_rent', 'Unknown')}
- Unit matched: {'Yes — ' + str(state.get('matched_unit_account')) if has_unit else 'No'}
- Tenant matched: {'Yes' if has_tenant else 'No'}
- Amount valid: {'Yes' if amount_ok else 'No'}
- Flag reason: {flag_reason}

Write a SHORT, clear, non-technical explanation (2-3 sentences max) for the landlord 
explaining WHY this payment was flagged and WHAT action they should take to resolve it.
Be specific and actionable. Mention the exact account number or phone number that didn't match."""

    response = await llm.ainvoke(prompt)
    ai_explanation = response.content

    return {
        **state,
        "decision": "flag",
        "flag_reason": flag_reason,
        "notes": f"Flagged for landlord review. Reason: {flag_reason}.",
        "ai_explanation": ai_explanation,
    }


# ── Routing ───────────────────────────────────────────────────────────────────

def route_after_account(state: ReconciliationState) -> str:
    """If account matched, skip phone matching."""
    return "validate_amount" if state.get("matched_unit_id") else "match_phone"


def route_after_phone(state: ReconciliationState) -> str:
    return "validate_amount" if state.get("matched_unit_id") else "decide"


# ── Build Graph ───────────────────────────────────────────────────────────────

def build_reconciliation_graph():
    """
    Construct and compile the LangGraph reconciliation workflow.
    Returns a compiled graph that accepts ReconciliationState.
    """
    builder = StateGraph(ReconciliationState)

    builder.add_node("match_account", match_account_node)
    builder.add_node("match_phone", match_phone_node)
    builder.add_node("validate_amount", validate_amount_node)
    builder.add_node("decide", decide_node)

    builder.add_edge(START, "match_account")
    builder.add_conditional_edges("match_account", route_after_account)
    builder.add_conditional_edges("match_phone", route_after_phone)
    builder.add_edge("validate_amount", "decide")
    builder.add_edge("decide", END)

    return builder.compile()


# Singleton graph — compiled once at startup
reconciliation_graph = build_reconciliation_graph()


# ── Public entry point ────────────────────────────────────────────────────────

async def run_reconciliation(
    *,
    db,
    landlord_id: str,
    payment_id: str,
    bill_ref_number: str,
    msisdn: str,
    amount: str,
    payer_name: str,
) -> ReconciliationState:
    """
    Run the full reconciliation workflow for one payment.
    Returns the final state with decision, flag_reason, notes, ai_explanation.
    """
    initial_state: ReconciliationState = {
        "landlord_id": landlord_id,
        "payment_id": payment_id,
        "bill_ref_number": bill_ref_number,
        "msisdn": msisdn,
        "amount": amount,
        "payer_name": payer_name,
        "matched_unit_id": None,
        "matched_unit_account": None,
        "expected_rent": None,
        "matched_tenant_id": None,
        "matched_tenant_phone": None,
        "decision": None,
        "flag_reason": None,
        "notes": "",
        "ai_explanation": None,
        "messages": [],
    }

    # Pass db into nodes via config (LangGraph runnable config)
    config = {"configurable": {"db": db}}

    final_state = await reconciliation_graph.ainvoke(initial_state, config=config)
    log.info(
        "reconciliation.complete",
        payment_id=payment_id,
        decision=final_state["decision"],
        flag_reason=final_state.get("flag_reason"),
    )
    return final_state
