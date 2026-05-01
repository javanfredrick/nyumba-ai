"""
Auth Router — /api/v1/auth
Handles: email/password register+login, Google OAuth2, JWT refresh.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.core.config import settings
from app.core.security import (
    verify_password, create_access_token, create_refresh_token, decode_refresh_token
)
from app.core.dependencies import get_db, CurrentLandlord
from app.schemas.schemas import (
    LandlordRegister, LandlordLogin, TokenResponse, RefreshRequest, LandlordResponse
)
from app.services.landlord_service import landlord_service

router = APIRouter(prefix="/auth", tags=["Auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def _build_tokens(landlord) -> TokenResponse:
    access = create_access_token(
        subject=landlord.email,
        landlord_id=str(landlord.id),
    )
    refresh = create_refresh_token(subject=landlord.email)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ── Email / Password ──────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: LandlordRegister, db: AsyncSession = Depends(get_db)):
    if await landlord_service.get_by_email(db, data.email):
        raise HTTPException(status_code=400, detail="Email already registered.")
    landlord = await landlord_service.create(db, data)
    await db.commit()
    return _build_tokens(landlord)


@router.post("/login", response_model=TokenResponse)
async def login(data: LandlordLogin, db: AsyncSession = Depends(get_db)):
    landlord = await landlord_service.get_by_email(db, data.email)
    if not landlord or not landlord.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    if not verify_password(data.password, landlord.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    if not landlord.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled.")
    return _build_tokens(landlord)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_refresh_token(data.refresh_token)
    landlord = await landlord_service.get_by_email(db, payload["sub"])
    if not landlord or not landlord.is_active:
        raise HTTPException(status_code=401, detail="Invalid refresh token.")
    return _build_tokens(landlord)


# ── Google OAuth2 ─────────────────────────────────────────────────────────────

@router.get("/google")
async def google_login():
    """Redirect browser to Google consent screen."""
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{query}")


@router.get("/google/callback", response_model=TokenResponse)
async def google_callback(code: str, db: AsyncSession = Depends(get_db)):
    """Exchange Google auth code for user info, then issue JWT."""
    async with httpx.AsyncClient() as client:
        # Exchange code for tokens
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Google token exchange failed.")
        google_tokens = token_resp.json()

        # Fetch user profile
        user_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {google_tokens['access_token']}"},
        )
        user_info = user_resp.json()

    sub = user_info["sub"]
    email = user_info["email"]
    name = user_info.get("name", email)
    avatar = user_info.get("picture")

    # Find or create landlord
    landlord = await landlord_service.get_by_google_sub(db, sub)
    if not landlord:
        landlord = await landlord_service.get_by_email(db, email)
        if landlord:
            # Link Google to existing email account
            landlord.google_sub = sub
            landlord.avatar_url = avatar
        else:
            landlord = await landlord_service.create_from_google(db, sub, email, name, avatar)
    await db.commit()
    return _build_tokens(landlord)


# ── Profile ───────────────────────────────────────────────────────────────────

@router.get("/me", response_model=LandlordResponse)
async def get_me(landlord: CurrentLandlord):
    return landlord
