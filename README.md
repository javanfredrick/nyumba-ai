# NyumbaAI 🏠

> **Intelligent Multi-Tenant Property Management System for Kenya**  
> Automated M-Pesa rent/mortgage reconciliation powered by LangGraph + Gemini AI

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React + Vite)                   │
│  Dashboard · Properties · Tenants · Payments · Flags · AI Chat  │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTPS / REST API
┌─────────────────────────▼───────────────────────────────────────┐
│                     BACKEND (FastAPI / Python 3.12)              │
│                                                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐ │
│  │  Auth Layer  │  │ M-Pesa Layer │  │      AI Layer           │ │
│  │  JWT + OAuth │  │ Daraja C2B   │  │  LangGraph Agent        │ │
│  │  Google SSO  │  │ Validation   │  │  LangChain RAG          │ │
│  └─────────────┘  │ Confirmation  │  │  Gemini 1.5 Flash       │ │
│                   └──────────────┘  │  ChromaDB Vector Store   │ │
│                                     └─────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              PostgreSQL (Row-Level Security)                  │ │
│  │  landlords · properties · units · tenants · leases          │ │
│  │  payments · payment_flags · mortgages · ai_usage_logs       │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Key Features

- **M-Pesa Daraja C2B Integration** — Auto-receives payments via Validation + Confirmation callbacks
- **Anti-Black-Book Gate** — Validation endpoint rejects any payment with an unknown account number
- **LangGraph Reconciliation Agent** — Stateful AI workflow matches each payment to the correct unit/tenant
- **RAG-Powered Q&A** — Landlords can ask natural language questions about their portfolio
- **Multi-Tenant RLS** — PostgreSQL Row-Level Security ensures complete landlord data isolation
- **Tiered Subscriptions** — Stripe-powered Starter/Growth/Enterprise plans with token metering
- **Mortgage Amortization** — Full reducing-balance schedule calculator for mortgage-type leases

## Project Structure

```
nyumba-ai/
├── backend/
│   ├── app/
│   │   ├── ai/
│   │   │   ├── agents/reconciliation_agent.py  # LangGraph state machine
│   │   │   └── chains/rag_chain.py             # LangChain RAG + ChromaDB
│   │   ├── api/v1/endpoints/
│   │   │   ├── auth.py        # JWT + Google OAuth2
│   │   │   ├── mpesa.py       # Daraja callbacks (validation/confirmation)
│   │   │   ├── properties.py  # Properties + Units CRUD
│   │   │   ├── tenants.py     # Tenants + Leases + Mortgages
│   │   │   ├── dashboard.py   # Aggregated stats
│   │   │   ├── ai.py          # RAG queries + token usage
│   │   │   └── billing.py     # Stripe subscriptions + webhooks
│   │   ├── core/
│   │   │   ├── config.py      # All settings (pydantic-settings)
│   │   │   ├── security.py    # JWT creation/verification
│   │   │   └── dependencies.py # Auth guards + quota checks
│   │   ├── db/
│   │   │   ├── session.py     # Async SQLAlchemy engine
│   │   │   └── rls.py         # PostgreSQL RLS helpers
│   │   ├── models/landlord.py # All ORM models
│   │   ├── schemas/schemas.py # Pydantic v2 schemas
│   │   ├── services/          # Business logic layer
│   │   ├── worker.py          # Celery background tasks
│   │   └── main.py            # FastAPI app factory
│   ├── alembic/               # Database migrations
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/             # All page components
│   │   ├── components/layout/ # Sidebar + App shell
│   │   ├── stores/authStore   # Zustand auth state
│   │   └── lib/api.ts         # Axios client + JWT interceptor
│   ├── tailwind.config.js
│   └── Dockerfile
├── nginx/nginx.conf
├── docker-compose.yml
├── CONFIG.md                  # All env vars documented
└── DEPLOYMENT.md              # AWS step-by-step guide
```

## Quick Start (Local Development)

### Prerequisites
- Python 3.12+
- Node.js 20+
- PostgreSQL 16+
- Redis 7+
- [ngrok](https://ngrok.com) (for M-Pesa callbacks in dev)

### 1. Clone and configure
```bash
git clone https://github.com/your-org/nyumba-ai.git
cd nyumba-ai
cp .env.template .env
# Edit .env with your API keys (see CONFIG.md)
```

### 2. Backend setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend setup
```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173
```

### 4. Start Celery worker (optional, for background tasks)
```bash
cd backend
celery -A app.worker worker --loglevel=info
celery -A app.worker beat --loglevel=info   # Scheduler
```

### 5. Expose for M-Pesa callbacks
```bash
ngrok http 8000
# Copy the HTTPS URL → set APP_BASE_URL in .env
```

## Docker (Full Stack)
```bash
cp .env.template .env   # Fill in values
docker compose up --build
# Frontend: http://localhost
# API:      http://localhost:8000
# API Docs: http://localhost:8000/api/v1/docs
```

## M-Pesa Payment Flow

```
Tenant dials *247# → enters Paybill + Account No (e.g. A3B) + Amount
         │
         ▼
Safaricom calls → POST /api/v1/mpesa/callback/{landlord_id}/validation
         │
         ├─ Account No known? ──NO──▶ Return C2B00011 (REJECT) ◀── BLACK BOOK BLOCKED
         │
         └─ YES ──▶ Return 0 (ACCEPT)
                      │
                      ▼
         Safaricom debits tenant → calls confirmation endpoint
                      │
                      ▼
         Payment saved as PENDING
                      │
                      ▼
         LangGraph Agent runs:
           1. match_account (BillRefNumber → Unit)
           2. match_phone   (MSISDN → Tenant)
           3. validate_amount (within 5% tolerance)
           4. decide: COMPLETE or FLAG with AI explanation
                      │
         ┌────────────┴────────────┐
         ▼                         ▼
    COMPLETED                   FLAGGED
  Unit credited            Landlord notified
  RAG re-indexed           in Flags dashboard
```

## Environment Setup Summary

See **CONFIG.md** for the full list. Key items:

| API | Where to Get |
|---|---|
| `GOOGLE_API_KEY` | [AI Studio](https://aistudio.google.com/app/apikey) |
| `GOOGLE_CLIENT_ID/SECRET` | [Google Cloud Console](https://console.cloud.google.com) |
| `MPESA_CONSUMER_KEY/SECRET` | [Safaricom Developer Portal](https://developer.safaricom.co.ke) |
| `LANGCHAIN_API_KEY` | [LangSmith](https://smith.langchain.com) |
| `STRIPE_SECRET_KEY` | [Stripe Dashboard](https://dashboard.stripe.com) |

## Deployment

See **DEPLOYMENT.md** for the complete step-by-step AWS Free Tier guide.

---

Built for the Kenyan proptech market 🇰🇪 — powered by M-Pesa, Gemini AI, and LangGraph.
