"""
NyumbaAI — FastAPI Application Entry Point
"""
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine, Base
from app.api.v1.endpoints import auth, properties, mpesa, ai, dashboard, tenants, billing

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    log.info("nyumba.startup", environment=settings.ENVIRONMENT)
    # Create all tables (use Alembic in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("nyumba.db_ready")
    yield
    await engine.dispose()
    log.info("nyumba.shutdown")


app = FastAPI(
    title="NyumbaAI API",
    description="Multi-tenant Property Management with M-Pesa + AI — Kenya",
    version=settings.APP_VERSION,
    docs_url=f"{settings.API_V1_STR}/docs" if settings.DEBUG else None,
    redoc_url=f"{settings.API_V1_STR}/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
PREFIX = settings.API_V1_STR
app.include_router(auth.router,       prefix=PREFIX)
app.include_router(properties.router, prefix=PREFIX)
app.include_router(mpesa.router,      prefix=PREFIX)
app.include_router(ai.router,         prefix=PREFIX)
app.include_router(dashboard.router,  prefix=PREFIX)
app.include_router(tenants.router,    prefix=PREFIX)
app.include_router(billing.router,    prefix=PREFIX)

# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error. Please try again."},
    )

# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "version": settings.APP_VERSION, "env": settings.ENVIRONMENT}
