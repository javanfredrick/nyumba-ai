"""
Celery Worker — background tasks:
  - Scheduled RAG re-indexing for all landlords
  - Monthly payment reminder emails (stub)
  - Overdue rent detection
"""
import asyncio
from celery import Celery
from celery.schedules import crontab
import structlog

from app.core.config import settings

log = structlog.get_logger(__name__)

celery_app = Celery(
    "nyumba_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.worker"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Africa/Nairobi",
    enable_utc=True,
    beat_schedule={
        # Re-index all landlord data into ChromaDB every 6 hours
        "reindex-all-landlords": {
            "task": "app.worker.reindex_all_landlords",
            "schedule": crontab(minute=0, hour="*/6"),
        },
        # Check for overdue payments every day at 8 AM Nairobi time
        "check-overdue-payments": {
            "task": "app.worker.check_overdue_payments",
            "schedule": crontab(minute=0, hour=8),
        },
    },
)


def run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.worker.reindex_all_landlords", bind=True, max_retries=3)
def reindex_all_landlords(self):
    """Re-seed ChromaDB vector store for every active landlord."""
    async def _run():
        from sqlalchemy import select
        from app.db.session import AsyncSessionLocal
        from app.models.landlord import Landlord
        from app.ai.chains.rag_chain import seed_vector_store

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Landlord).where(Landlord.is_active == True)
            )
            landlords = result.scalars().all()
            log.info("worker.reindex_start", count=len(landlords))

            for landlord in landlords:
                try:
                    count = await seed_vector_store(db, str(landlord.id))
                    log.info("worker.reindexed", landlord_id=str(landlord.id), docs=count)
                except Exception as e:
                    log.error("worker.reindex_failed", landlord_id=str(landlord.id), error=str(e))

    run_async(_run())


@celery_app.task(name="app.worker.check_overdue_payments", bind=True, max_retries=3)
def check_overdue_payments(self):
    """
    Flag leases where no payment has been received this calendar month.
    Creates an AI usage log entry summarizing overdue units per landlord.
    """
    async def _run():
        from sqlalchemy import select, func
        from datetime import date, datetime, timezone
        from app.db.session import AsyncSessionLocal
        from app.models.landlord import Landlord, Lease, Payment, PaymentStatus

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Landlord).where(Landlord.is_active == True)
            )
            landlords = result.scalars().all()

            for landlord in landlords:
                # Get all active leases
                leases = (await db.execute(
                    select(Lease).where(
                        Lease.landlord_id == landlord.id,
                        Lease.is_active == True,
                    )
                )).scalars().all()

                # Get payments this month
                paid_units = (await db.execute(
                    select(Payment.unit_id).where(
                        Payment.landlord_id == landlord.id,
                        Payment.status == PaymentStatus.COMPLETED,
                        func.date_trunc("month", Payment.transaction_date)
                        == func.date_trunc("month", func.now()),
                    )
                )).scalars().all()

                paid_unit_ids = set(paid_units)
                overdue = [l for l in leases if l.unit_id not in paid_unit_ids]

                if overdue:
                    log.warning(
                        "worker.overdue_detected",
                        landlord_id=str(landlord.id),
                        overdue_count=len(overdue),
                        lease_ids=[str(l.id) for l in overdue],
                    )
                    # TODO: Send email/SMS notification to landlord

    run_async(_run())


@celery_app.task(name="app.worker.reconcile_payment", bind=True, max_retries=3)
def reconcile_payment_task(self, payment_id: str, landlord_id: str):
    """
    Alternative: run reconciliation as a Celery task instead of inline.
    Useful for high-throughput scenarios.
    """
    async def _run():
        from uuid import UUID
        from app.db.session import AsyncSessionLocal
        from app.services.payment_service import payment_service
        from app.models.landlord import Payment
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Payment).where(Payment.id == UUID(payment_id))
            )
            payment = result.scalar_one_or_none()
            if not payment:
                log.error("worker.payment_not_found", payment_id=payment_id)
                return

            log.info("worker.reconcile_start", payment_id=payment_id)
            # Reconciliation logic runs inline in the callback endpoint for now

    run_async(_run())
