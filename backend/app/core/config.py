"""
Core configuration — loads from environment variables / .env file.
All sensitive values are placeholders; see CONFIG.md for details.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, field_validator
from typing import List, Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "NyumbaAI"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"          # development | staging | production
    DEBUG: bool = False
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_USE_OPENSSL_RAND_HEX_32"
    API_V1_STR: str = "/api/v1"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── Database ─────────────────────────────────────────────────────────────
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "nyumba_db"
    POSTGRES_USER: str = "nyumba_user"
    POSTGRES_PASSWORD: str = "CHANGE_ME_DB_PASSWORD"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── JWT Auth ─────────────────────────────────────────────────────────────
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── Google OAuth2 ────────────────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = "YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com"
    GOOGLE_CLIENT_SECRET: str = "YOUR_GOOGLE_CLIENT_SECRET"
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    # ── Gemini AI ────────────────────────────────────────────────────────────
    GOOGLE_API_KEY: str = "YOUR_GEMINI_API_KEY"          # AIza...
    GEMINI_MODEL: str = "gemini-1.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "models/embedding-001"

    # ── LangSmith Tracing ────────────────────────────────────────────────────
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_API_KEY: str = "YOUR_LANGSMITH_API_KEY"   # ls__...
    LANGCHAIN_PROJECT: str = "nyumba-ai-production"
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"

    # ── M-Pesa Daraja API ────────────────────────────────────────────────────
    MPESA_ENVIRONMENT: str = "sandbox"                   # sandbox | production
    MPESA_CONSUMER_KEY: str = "YOUR_SAFARICOM_CONSUMER_KEY"
    MPESA_CONSUMER_SECRET: str = "YOUR_SAFARICOM_CONSUMER_SECRET"
    MPESA_SHORTCODE: str = "174379"                      # Paybill / Till
    MPESA_PASSKEY: str = "YOUR_MPESA_PASSKEY"
    MPESA_INITIATOR_NAME: str = "YOUR_INITIATOR_NAME"
    MPESA_INITIATOR_PASSWORD: str = "YOUR_INITIATOR_PASSWORD"
    # Public-facing base URL (ngrok in dev, your domain in prod)
    APP_BASE_URL: str = "https://your-domain.com"

    @property
    def MPESA_BASE_URL(self) -> str:
        if self.MPESA_ENVIRONMENT == "production":
            return "https://api.safaricom.co.ke"
        return "https://sandbox.safaricom.co.ke"

    @property
    def MPESA_CALLBACK_BASE(self) -> str:
        """Landlord-specific callback URL injected with landlord_id."""
        return f"{self.APP_BASE_URL}/api/v1/mpesa/callback"

    # ── Redis (Celery broker + cache) ─────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Stripe (Subscription billing) ────────────────────────────────────────
    STRIPE_SECRET_KEY: str = "sk_test_YOUR_STRIPE_SECRET_KEY"
    STRIPE_WEBHOOK_SECRET: str = "whsec_YOUR_STRIPE_WEBHOOK_SECRET"
    STRIPE_PUBLISHABLE_KEY: str = "pk_test_YOUR_STRIPE_PUBLISHABLE_KEY"

    # ── Subscription Tier Limits ──────────────────────────────────────────────
    TIER_STARTER_MAX_UNITS: int = 10
    TIER_GROWTH_MAX_UNITS: int = 50
    TIER_ENTERPRISE_MAX_UNITS: int = 99999   # Unlimited

    # ── AI Token Metering (KES per 1K tokens) ────────────────────────────────
    AI_TOKEN_COST_PER_1K: float = 0.50      # KES 0.50 per 1K tokens


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
