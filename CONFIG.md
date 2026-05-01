# CONFIG.md — NyumbaAI Environment Variables & Secrets

This document lists every environment variable, where to get it, and what it controls.  
**Never commit `.env` to Git.** Use `.env.template` as your starting point.

---

## 1. App Core

| Variable | Example | Description |
|---|---|---|
| `APP_NAME` | `NyumbaAI` | Application display name |
| `ENVIRONMENT` | `development` / `production` | Controls debug mode, API docs visibility |
| `DEBUG` | `false` | Set `true` only in development |
| `SECRET_KEY` | 64-char hex string | JWT signing key. Generate: `openssl rand -hex 32` |

---

## 2. PostgreSQL Database

| Variable | Example | Where to Get |
|---|---|---|
| `POSTGRES_HOST` | `localhost` or `db` (Docker) | Your DB server hostname |
| `POSTGRES_PORT` | `5432` | Default PostgreSQL port |
| `POSTGRES_DB` | `nyumba_db` | Database name (create it first) |
| `POSTGRES_USER` | `nyumba_user` | DB user with full privileges |
| `POSTGRES_PASSWORD` | strong password | Set during PostgreSQL setup |

**Setup commands:**
```sql
CREATE DATABASE nyumba_db;
CREATE USER nyumba_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE nyumba_db TO nyumba_user;
```

---

## 3. Google OAuth2 (Sign in with Google)

| Variable | Where to Get |
|---|---|
| `GOOGLE_CLIENT_ID` | [Google Cloud Console](https://console.cloud.google.com) → APIs & Services → Credentials → OAuth 2.0 Client ID |
| `GOOGLE_CLIENT_SECRET` | Same as above |
| `GOOGLE_REDIRECT_URI` | Must match exactly what you register in Google Console. Dev: `http://localhost:8000/api/v1/auth/google/callback` |

**Steps:**
1. Go to Google Cloud Console → Create Project
2. Enable **Google+ API** and **Google Identity**
3. Create OAuth 2.0 credentials (Web Application type)
4. Add your redirect URI to Authorized Redirect URIs

---

## 4. Gemini AI (Google)

| Variable | Where to Get |
|---|---|
| `GOOGLE_API_KEY` | [Google AI Studio](https://aistudio.google.com/app/apikey) → Create API Key |

- Model used: `gemini-1.5-flash` (fast, cost-effective)
- Embedding model: `models/embedding-001`
- Free tier includes 15 RPM and 1M tokens/day on Flash

---

## 5. LangSmith (AI Tracing)

| Variable | Where to Get |
|---|---|
| `LANGCHAIN_API_KEY` | [LangSmith](https://smith.langchain.com) → Settings → API Keys |
| `LANGCHAIN_PROJECT` | Your project name in LangSmith (e.g. `nyumba-ai-production`) |
| `LANGCHAIN_TRACING_V2` | Set `true` to enable tracing, `false` to disable |

---

## 6. M-Pesa Daraja API (Safaricom)

| Variable | Where to Get | Notes |
|---|---|---|
| `MPESA_ENVIRONMENT` | — | `sandbox` for testing, `production` for live |
| `MPESA_CONSUMER_KEY` | [Safaricom Developer Portal](https://developer.safaricom.co.ke) → My Apps | Create app, choose C2B |
| `MPESA_CONSUMER_SECRET` | Same as above | |
| `MPESA_SHORTCODE` | Safaricom Business team or Sandbox: `174379` | Your Paybill/Till number |
| `MPESA_PASSKEY` | Provided by Safaricom with your Paybill | Used for STK Push password |
| `APP_BASE_URL` | Your public domain | e.g. `https://nyumba.yourdomain.com`. In dev: use ngrok |

**Dev ngrok setup:**
```bash
ngrok http 8000
# Copy the https URL → set as APP_BASE_URL
```

**Sandbox test credentials:**
- Shortcode: `174379`
- Test phone: `254708374149`
- Passkey: Available in Safaricom Developer Portal under STK Push

**C2B URL Registration** (run once after deployment):
```
POST /api/v1/mpesa/register/{landlord_id}
Authorization: Bearer <your_jwt>
```

---

## 7. Redis

| Variable | Example | Notes |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | Main cache |
| `CELERY_BROKER_URL` | `redis://localhost:6379/1` | Celery task queue |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/2` | Celery results |

In Docker Compose, use `redis://redis:6379/0`.

---

## 8. Stripe (Subscription Billing)

| Variable | Where to Get |
|---|---|
| `STRIPE_SECRET_KEY` | [Stripe Dashboard](https://dashboard.stripe.com) → Developers → API Keys |
| `STRIPE_PUBLISHABLE_KEY` | Same location (starts with `pk_`) |
| `STRIPE_WEBHOOK_SECRET` | Stripe Dashboard → Webhooks → Add endpoint → Signing secret |

**Subscription Tiers:**
| Tier | Max Units | Monthly Price |
|---|---|---|
| Starter | 10 | KES 2,500 |
| Growth | 50 | KES 7,500 |
| Enterprise | Unlimited | KES 20,000+ |

---

## 9. CORS Origins

```
ALLOWED_ORIGINS=["https://yourdomain.com","https://www.yourdomain.com"]
```

In development: `["http://localhost:5173","http://localhost:3000"]`

---

## Security Checklist Before Production

- [ ] `SECRET_KEY` is 64+ random characters (not the default)
- [ ] `DEBUG=false`
- [ ] `ENVIRONMENT=production`
- [ ] All passwords are strong and unique
- [ ] `.env` is in `.gitignore`
- [ ] PostgreSQL is not publicly accessible (only accessible within VPC/Docker network)
- [ ] Redis is password-protected or network-isolated
- [ ] M-Pesa is set to `production` environment
- [ ] HTTPS is enabled (via Nginx + Let's Encrypt or AWS ACM)
- [ ] LangSmith tracing project is separate for prod vs dev
