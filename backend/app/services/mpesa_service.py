"""
M-Pesa Daraja API Service.
Handles OAuth token generation, C2B registration, STK Push, and callback parsing.
All secrets loaded from settings — never hardcoded.
"""
import base64
import hashlib
from datetime import datetime
from typing import Optional
import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

log = structlog.get_logger(__name__)


class MpesaService:
    """Stateless service — one instance shared via dependency injection."""

    def __init__(self):
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    # ── Auth ──────────────────────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_access_token(self) -> str:
        """Fetch (or return cached) OAuth2 bearer token from Safaricom."""
        if self._access_token and self._token_expiry and datetime.utcnow() < self._token_expiry:
            return self._access_token

        credentials = base64.b64encode(
            f"{settings.MPESA_CONSUMER_KEY}:{settings.MPESA_CONSUMER_SECRET}".encode()
        ).decode()

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.MPESA_BASE_URL}/oauth/v1/generate?grant_type=client_credentials",
                headers={"Authorization": f"Basic {credentials}"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

        self._access_token = data["access_token"]
        # Token valid for 3600s; refresh 60s early
        from datetime import timedelta
        self._token_expiry = datetime.utcnow() + timedelta(seconds=3540)
        log.info("mpesa.token_refreshed")
        return self._access_token

    # ── C2B URL Registration (run once per go-live) ───────────────────────────

    async def register_c2b_urls(self, landlord_id: str, shortcode: Optional[str] = None) -> dict:
        """
        Register Validation + Confirmation URLs for a landlord's shortcode.
        landlord_id is embedded in the URL path for multi-tenant routing.
        """
        token = await self.get_access_token()
        sc = shortcode or settings.MPESA_SHORTCODE
        base = settings.MPESA_CALLBACK_BASE

        payload = {
            "ShortCode": sc,
            "ResponseType": "Completed",   # "Cancelled" to reject unvalidated
            "ConfirmationURL": f"{base}/{landlord_id}/confirmation",
            "ValidationURL": f"{base}/{landlord_id}/validation",
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.MPESA_BASE_URL}/mpesa/c2b/v1/registerurl",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=20,
            )
            resp.raise_for_status()
            result = resp.json()

        log.info("mpesa.c2b_registered", landlord_id=landlord_id, shortcode=sc, result=result)
        return result

    # ── STK Push (Lipa Na M-Pesa Online) ─────────────────────────────────────

    async def stk_push(
        self,
        phone: str,
        amount: int,
        account_reference: str,
        transaction_desc: str,
        landlord_id: str,
    ) -> dict:
        """Initiate STK Push prompt on tenant's phone."""
        token = await self.get_access_token()
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(
            f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}".encode()
        ).decode()

        payload = {
            "BusinessShortCode": settings.MPESA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone,
            "PartyB": settings.MPESA_SHORTCODE,
            "PhoneNumber": phone,
            "CallBackURL": f"{settings.MPESA_CALLBACK_BASE}/{landlord_id}/stk",
            "AccountReference": account_reference,
            "TransactionDesc": transaction_desc,
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.MPESA_BASE_URL}/mpesa/stkpush/v1/processrequest",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=20,
            )
            resp.raise_for_status()
            return resp.json()

    # ── Validation Logic (called by our endpoint before confirming) ───────────

    def validate_callback_security(self, raw_body: bytes, x_mpesa_signature: str) -> bool:
        """
        Verify Safaricom HMAC signature on incoming callbacks.
        Prevents forged "Black Book" manual entries.
        Returns True if signature is valid.
        """
        expected = hashlib.sha256(
            f"{settings.MPESA_CONSUMER_SECRET}{raw_body.decode()}".encode()
        ).hexdigest()
        return hmac.compare_digest(expected, x_mpesa_signature)

    def parse_transaction_time(self, ts: str) -> datetime:
        """Parse M-Pesa TransTime format: YYYYMMDDHHmmss → datetime."""
        return datetime.strptime(ts, "%Y%m%d%H%M%S")


import hmac  # noqa: E402 — placed here to keep imports clean above

mpesa_service = MpesaService()
