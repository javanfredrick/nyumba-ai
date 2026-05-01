"""
RAG Chain — Landlord Q&A powered by LangChain + Gemini + ChromaDB.
Landlords can ask questions like:
  "Which tenants are overdue this month?"
  "Show me all flagged payments for Apartment 3B"
  "What is the outstanding mortgage balance for John Kamau?"

The chain retrieves relevant context from ChromaDB (seeded with the
landlord's property/payment data as documents) and answers via Gemini.
"""
from __future__ import annotations

import os
from typing import Optional
from uuid import UUID

import structlog
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_community.vectorstores import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain.schema import Document

from app.core.config import settings

log = structlog.get_logger(__name__)

# ── Prompt ────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template="""You are NyumbaAI, an expert property management assistant for Kenyan landlords.
You have access to the landlord's property data, tenant records, and payment history below.

CONTEXT:
{context}

INSTRUCTIONS:
- Answer ONLY based on the context provided.
- If the answer is not in the context, say "I don't have enough data to answer that. Please check your dashboard."
- Always use Kenyan Shilling (KES) for monetary values.
- Be concise, professional, and actionable.
- Format lists with bullet points when listing multiple items.

QUESTION: {question}

ANSWER:""",
)


# ── ChromaDB collection name per landlord ─────────────────────────────────────

def _collection_name(landlord_id: str) -> str:
    return f"landlord_{landlord_id.replace('-', '')}"


# ── Embedding model ───────────────────────────────────────────────────────────

def _get_embeddings() -> GoogleGenerativeAIEmbeddings:
    return GoogleGenerativeAIEmbeddings(
        model=settings.GEMINI_EMBEDDING_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
    )


# ── Seed / refresh the vector store for a landlord ───────────────────────────

async def seed_vector_store(db, landlord_id: str) -> int:
    """
    Convert all landlord data to Document objects and upsert into ChromaDB.
    Returns the number of documents indexed.
    Called after every payment reconciliation and on schedule.
    """
    from sqlalchemy import select
    from app.models.landlord import Property, Unit, Tenant, Lease, Payment, PaymentStatus

    docs: list[Document] = []
    lid = UUID(landlord_id)

    # Properties
    props = (await db.execute(select(Property).where(Property.landlord_id == lid))).scalars().all()
    for p in props:
        docs.append(Document(
            page_content=f"Property: {p.name} at {p.address}, {p.city}. Description: {p.description or 'N/A'}.",
            metadata={"type": "property", "id": str(p.id), "landlord_id": landlord_id},
        ))

    # Units
    units = (await db.execute(select(Unit).where(Unit.landlord_id == lid))).scalars().all()
    for u in units:
        docs.append(Document(
            page_content=(
                f"Unit {u.unit_number} (Account: {u.account_number}): "
                f"{u.bedrooms}BR/{u.bathrooms}BA, Rent KES {u.monthly_rent}/month. "
                f"Status: {'Occupied' if u.is_occupied else 'Vacant'}."
            ),
            metadata={"type": "unit", "id": str(u.id), "landlord_id": landlord_id},
        ))

    # Tenants
    tenants = (await db.execute(select(Tenant).where(Tenant.landlord_id == lid))).scalars().all()
    for t in tenants:
        docs.append(Document(
            page_content=(
                f"Tenant: {t.full_name}, Phone: {t.phone}, Email: {t.email or 'N/A'}. "
                f"Status: {'Active' if t.is_active else 'Inactive'}."
            ),
            metadata={"type": "tenant", "id": str(t.id), "landlord_id": landlord_id},
        ))

    # Recent payments (last 90 days)
    payments = (
        await db.execute(
            select(Payment)
            .where(Payment.landlord_id == lid)
            .order_by(Payment.transaction_date.desc())
            .limit(200)
        )
    ).scalars().all()
    for p in payments:
        docs.append(Document(
            page_content=(
                f"Payment {p.mpesa_receipt_number}: KES {p.amount} from {p.msisdn} "
                f"({p.first_name} {p.last_name or ''}). "
                f"Account quoted: {p.bill_ref_number}. "
                f"Status: {p.status.value}. Date: {p.transaction_date.strftime('%d %b %Y')}. "
                f"Notes: {p.reconciliation_notes or 'None'}."
            ),
            metadata={"type": "payment", "id": str(p.id), "landlord_id": landlord_id},
        ))

    if not docs:
        return 0

    embeddings = _get_embeddings()
    Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name=_collection_name(landlord_id),
        persist_directory="./chroma_db",
    )
    log.info("rag.vector_store_seeded", landlord_id=landlord_id, doc_count=len(docs))
    return len(docs)


# ── Query ─────────────────────────────────────────────────────────────────────

async def query_landlord_rag(
    landlord_id: str,
    question: str,
) -> dict:
    """
    Run a RAG query against the landlord's vector store.
    Returns answer, source references, and token usage.
    """
    embeddings = _get_embeddings()
    collection = _collection_name(landlord_id)

    try:
        vectorstore = Chroma(
            collection_name=collection,
            embedding_function=embeddings,
            persist_directory="./chroma_db",
        )
    except Exception as e:
        log.error("rag.vectorstore_load_failed", error=str(e))
        return {
            "answer": "I don't have any data indexed yet. Please ensure your properties and payments are set up.",
            "sources": [],
            "tokens_used": 0,
            "cost_kes": 0.0,
        }

    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 5, "filter": {"landlord_id": landlord_id}},
    )

    llm = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.2,
    )

    chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True,
        chain_type_kwargs={"prompt": SYSTEM_PROMPT},
    )

    with_callback = chain.with_config({"run_name": f"rag_query_{landlord_id[:8]}"})
    result = await with_callback.ainvoke({"query": question})

    # Extract sources
    sources = list({
        doc.metadata.get("type", "unknown") + ":" + doc.metadata.get("id", "")[:8]
        for doc in result.get("source_documents", [])
    })

    # Estimate token cost (Gemini Flash ~$0.075/1M input, $0.30/1M output)
    # We approximate using character count / 4 chars per token
    estimated_tokens = len(question) // 4 + len(result["result"]) // 4
    cost_kes = (estimated_tokens / 1000) * settings.AI_TOKEN_COST_PER_1K

    return {
        "answer": result["result"],
        "sources": sources,
        "tokens_used": estimated_tokens,
        "cost_kes": round(cost_kes, 4),
    }
