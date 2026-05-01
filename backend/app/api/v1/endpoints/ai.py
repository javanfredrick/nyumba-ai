"""AI Router — /api/v1/ai  (RAG queries + usage stats)"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.dependencies import get_db, CurrentLandlord
from app.schemas.schemas import AIQueryRequest, AIQueryResponse
from app.ai.chains.rag_chain import query_landlord_rag, seed_vector_store
from app.models.landlord import AIUsageLog
from app.services.landlord_service import landlord_service
from app.core.config import settings

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/query", response_model=AIQueryResponse)
async def ai_query(
    data: AIQueryRequest,
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """RAG-powered natural language query against landlord's property data."""

    # Token quota check
    if landlord.ai_tokens_used >= landlord.ai_tokens_limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="AI token quota exhausted. Please upgrade your plan.",
        )

    result = await query_landlord_rag(
        landlord_id=str(landlord.id),
        question=data.question,
    )

    # Meter token usage
    tokens = result["tokens_used"]
    cost = result["cost_kes"]
    await landlord_service.increment_ai_tokens(db, landlord.id, tokens)

    # Persist usage log
    log_entry = AIUsageLog(
        landlord_id=landlord.id,
        operation="rag_query",
        prompt_tokens=tokens // 2,
        completion_tokens=tokens // 2,
        total_tokens=tokens,
        cost_kes=cost,
    )
    db.add(log_entry)
    await db.commit()

    return AIQueryResponse(**result)


@router.post("/seed", status_code=status.HTTP_202_ACCEPTED)
async def seed_rag(
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger re-indexing of landlord data into the vector store."""
    doc_count = await seed_vector_store(db, str(landlord.id))
    return {"message": f"Indexed {doc_count} documents successfully."}


@router.get("/usage")
async def get_ai_usage(
    landlord: CurrentLandlord = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Return token usage stats and recent AI operation logs."""
    logs = (
        await db.execute(
            select(AIUsageLog)
            .where(AIUsageLog.landlord_id == landlord.id)
            .order_by(AIUsageLog.created_at.desc())
            .limit(20)
        )
    ).scalars().all()

    return {
        "tokens_used": landlord.ai_tokens_used,
        "tokens_limit": landlord.ai_tokens_limit,
        "tokens_remaining": max(0, landlord.ai_tokens_limit - landlord.ai_tokens_used),
        "usage_percent": round(landlord.ai_tokens_used / landlord.ai_tokens_limit * 100, 1),
        "cost_per_1k_tokens_kes": settings.AI_TOKEN_COST_PER_1K,
        "recent_operations": [
            {
                "operation": l.operation,
                "tokens": l.total_tokens,
                "cost_kes": float(l.cost_kes),
                "at": l.created_at.isoformat(),
            }
            for l in logs
        ],
    }
