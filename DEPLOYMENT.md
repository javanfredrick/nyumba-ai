# DEPLOYMENT.md — NyumbaAI Production Deployment Guide

**Target:** AWS Free Tier — EC2 t2.micro (or Lightsail $5/mo) + Docker Compose  
**Domain:** Assumed you own a domain (e.g. via Namecheap). Can also use the EC2 public IP temporarily.

---

## Step 1 — Provision EC2 Instance

### Option A: EC2 Free Tier
1. Go to **AWS Console → EC2 → Launch Instance**
2. Choose **Ubuntu Server 24.04 LTS** (Free tier eligible)
3. Instance type: `t2.micro` (1 vCPU, 1GB RAM — enough for MVP)
4. Storage: **20GB gp3** (Free tier gives 30GB)
5. Security Group — open these ports:
   - `22` (SSH) — your IP only
   - `80` (HTTP) — 0.0.0.0/0
   - `443` (HTTPS) — 0.0.0.0/0
   - `8000` (API, optional) — your IP only for debugging
6. Create or select a key pair, download `.pem`
7. Launch instance

### Option B: Lightsail (Simpler, $5/mo)
1. AWS Console → Lightsail → Create Instance
2. OS: Ubuntu 22.04
3. Plan: $5/mo (1GB RAM, 40GB SSD, 2TB transfer)
4. Add static IP (free while attached)

---

## Step 2 — Connect & Configure Server

```bash
# Connect via SSH
chmod 400 your-key.pem
ssh -i your-key.pem ubuntu@YOUR_EC2_PUBLIC_IP

# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu
newgrp docker

# Install Docker Compose v2
sudo apt install docker-compose-plugin -y
docker compose version  # Verify
```

---

## Step 3 — Upload Your Code

### From your local machine:
```bash
# Create a deployment archive (exclude node_modules, .git, __pycache__)
tar --exclude='./frontend/node_modules' \
    --exclude='./.git' \
    --exclude='./backend/__pycache__' \
    -czf nyumba.tar.gz .

# Upload to EC2
scp -i your-key.pem nyumba.tar.gz ubuntu@YOUR_EC2_IP:~/

# On the server
mkdir -p ~/nyumba && cd ~/nyumba
tar -xzf ~/nyumba.tar.gz
```

### Or clone from Git:
```bash
git clone https://github.com/your-org/nyumba-ai.git ~/nyumba
cd ~/nyumba
```

---

## Step 4 — Configure Environment

```bash
cd ~/nyumba

# Copy template and fill in all values
cp .env.template .env
nano .env
```

**Critical values to change:**
```bash
SECRET_KEY=$(openssl rand -hex 32)  # Generate and paste
ENVIRONMENT=production
DEBUG=false
POSTGRES_PASSWORD=<strong_random_password>
APP_BASE_URL=https://yourdomain.com
MPESA_ENVIRONMENT=production
```

---

## Step 5 — Set Up DNS (Skip if using IP)

1. In your domain registrar (Namecheap, GoDaddy, Cloudflare):
   - Add **A Record**: `@` → `YOUR_EC2_PUBLIC_IP`
   - Add **A Record**: `www` → `YOUR_EC2_PUBLIC_IP`
2. Wait for DNS propagation (5–30 mins)
3. Verify: `nslookup yourdomain.com`

---

## Step 6 — SSL Certificate (HTTPS)

```bash
# Install Certbot
sudo apt install certbot -y

# Stop Nginx if running
docker compose stop frontend

# Get certificate (answer prompts)
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Certificates will be at:
# /etc/letsencrypt/live/yourdomain.com/fullchain.pem
# /etc/letsencrypt/live/yourdomain.com/privkey.pem
```

**Update nginx.conf to add HTTPS** (create `nginx/nginx-ssl.conf`):
```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # ... rest of your nginx config
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$host$request_uri;
}
```

Mount cert in docker-compose.yml under `frontend` service:
```yaml
volumes:
  - /etc/letsencrypt:/etc/letsencrypt:ro
```

**Auto-renew SSL:**
```bash
echo "0 12 * * * root certbot renew --quiet && docker compose -f ~/nyumba/docker-compose.yml restart frontend" | sudo tee -a /etc/crontab
```

---

## Step 7 — Launch the Stack

```bash
cd ~/nyumba

# Build all images
docker compose build

# Start all services (detached)
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f backend
docker compose logs -f frontend
```

---

## Step 8 — Run Database Migrations

```bash
# One-time: run Alembic migrations inside backend container
docker compose exec backend alembic upgrade head

# Verify tables exist
docker compose exec db psql -U nyumba_user -d nyumba_db -c "\dt"
```

---

## Step 9 — Register M-Pesa C2B URLs

After deployment, for each landlord who signs up, call this endpoint:

```bash
curl -X POST https://yourdomain.com/api/v1/mpesa/register/<LANDLORD_ID> \
  -H "Authorization: Bearer <LANDLORD_JWT>"
```

This tells Safaricom where to send payment callbacks.  
**Do this once per landlord per environment (sandbox / production).**

---

## Step 10 — Set Up Monitoring

```bash
# Basic: watch container health
watch -n 5 docker compose ps

# View real-time logs
docker compose logs -f --tail=50

# Install htop for resource monitoring
sudo apt install htop -y
htop
```

**Optional — Set up UptimeRobot (free):**
1. Go to [uptimerobot.com](https://uptimerobot.com)
2. Add HTTP monitor: `https://yourdomain.com/health`
3. Alert via email/Slack if down

---

## Common Operations

```bash
# Restart a service
docker compose restart backend

# Pull latest code and redeploy
git pull origin main
docker compose build backend frontend
docker compose up -d --no-deps backend frontend

# Backup database
docker compose exec db pg_dump -U nyumba_user nyumba_db > backup_$(date +%Y%m%d).sql

# Restore database
cat backup.sql | docker compose exec -T db psql -U nyumba_user nyumba_db

# Scale workers
docker compose up -d --scale worker=2

# Emergency: full restart
docker compose down && docker compose up -d
```

---

## Resource Estimates (t2.micro)

| Service | RAM | CPU |
|---|---|---|
| PostgreSQL | ~150MB | Low |
| Redis | ~10MB | Minimal |
| FastAPI (2 workers) | ~200MB | Medium |
| Celery worker | ~150MB | Medium |
| Nginx | ~5MB | Minimal |
| **Total** | **~515MB** | — |

t2.micro has 1GB RAM — workable for MVP with up to ~50 concurrent users.  
Upgrade to **t3.small** (2GB) when you hit consistent load.

---

## Estimated AWS Costs (Monthly)

| Service | Cost |
|---|---|
| EC2 t2.micro (Free Tier, 1 year) | $0 → $8.50/mo after |
| Lightsail 1GB | $5/mo always |
| EBS Storage 20GB | Free tier / ~$1.60 |
| Data Transfer (15GB) | Free tier |
| Elastic IP | Free while attached |
| **Total MVP** | **$0–$10/mo** |
