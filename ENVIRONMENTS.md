# SipSense: Environments & Deployment Guide

## The Three Environments

| Environment | Database | How to run | URL |
|-------------|----------|------------|-----|
| **Local dev** | SQLite | `uvicorn app.main:app --reload` + `npm run dev` | `http://localhost:5173` |
| **Staging** | PostgreSQL (Docker) | `./scripts/start-staging.sh` | `http://localhost:8080` or `https://staging.yourdomain.com` |
| **Production** | PostgreSQL (Docker) | `./scripts/start-production.sh` | `https://yourdomain.com` |

---

## Day-to-Day Workflow

```
1. Write code locally        (SQLite, hot-reload, fast iteration)
2. Run tests locally          cd backend && .venv/bin/pytest
3. Push branch, open PR       → GitHub Actions runs tests automatically
4. Merge PR to main           → Staging auto-deploys
5. Verify on staging          click around, test your feature with PostgreSQL
6. Deploy to production       GitHub Actions → Run workflow → select "production" → approve
```

---

## Quick Reference

### Local Development
```bash
# Backend (from backend/)
source .venv/bin/activate
uvicorn app.main:app --reload

# Frontend (from frontend/)
npm run dev
```

### Staging (Docker)
```bash
# First time: copy and fill in env template
cp env.staging.example .env.staging
# Edit .env.staging with real values

# Start
./scripts/start-staging.sh

# Seed database (first time only)
./scripts/seed-staging.sh

# Check health
curl http://localhost:8080/api/health
```

### Production (Docker)
```bash
# First time: copy and fill in env template
cp env.production.example .env.production
# Edit .env.production with real values

# Start
./scripts/start-production.sh

# Check health
curl http://localhost/api/health
```

### Database Operations
```bash
# Backup (before risky changes)
./scripts/backup-db.sh staging
./scripts/backup-db.sh production

# Create a migration after changing models.py
cd backend
.venv/bin/alembic revision --autogenerate -m "describe what changed"

# Apply migrations
.venv/bin/alembic upgrade head

# View migration history
.venv/bin/alembic history
```

---

## Environment Configuration

Each environment uses its own `.env` file:

| File | Tracked in git? | Purpose |
|------|-----------------|---------|
| `.env` | No | Local development |
| `.env.staging` | No | Staging server |
| `.env.production` | No | Production server |
| `.env.example` | Yes | Template for local dev |
| `env.staging.example` | Yes | Template for staging |
| `env.production.example` | Yes | Template for production |

Key variables that differ per environment:
- `SIPSENSE_ENV` — `development`, `staging`, or `production`
- `JWT_SECRET_KEY` — **must be unique per environment**
- `CORS_ORIGINS` — your domain for that environment
- `POSTGRES_PASSWORD` — **must be unique per environment**
- `RATE_LIMIT_MAX` — 100 for staging (easier to test), 300 for production

---

## CI/CD Pipeline

### Automatic (on every push/PR to main)
1. **Backend tests** — Python 3.11, pytest
2. **Frontend build** — Node 20, lint + build

### On merge to main
3. **Staging auto-deploy** — SSH to staging server, pull code, rebuild containers

### Manual trigger (GitHub Actions → Deploy → Run workflow)
4. **Production deploy** — Requires your approval in GitHub, backs up DB first

### Health monitoring
5. **Every 15 min** — GitHub Actions pings `/api/health` on both environments, emails you on failure

---

## GitHub Setup Checklist

Before CI/CD works, you need to configure these in your GitHub repo:

### Repository Secrets (Settings → Secrets and variables → Actions)
- [ ] `STAGING_SSH_KEY` — SSH private key for staging server
- [ ] `STAGING_HOST` — IP address or hostname of staging server
- [ ] `STAGING_URL` — Full URL like `https://staging.yourdomain.com`
- [ ] `PRODUCTION_SSH_KEY` — SSH private key for production server
- [ ] `PRODUCTION_HOST` — IP address or hostname of production server
- [ ] `PRODUCTION_URL` — Full URL like `https://yourdomain.com`

### Environments (Settings → Environments)
- [ ] Create `staging` environment (no restrictions needed)
- [ ] Create `production` environment → check "Required reviewers" → add yourself

---

## Docker Compose Architecture

The base `docker-compose.yml` defines all services. Environment-specific files override only what differs:

```
docker-compose.yml                  ← base (all services, no ports on frontend)
  + docker-compose.staging.yml      ← staging DB name, port 8080, .env.staging
  + docker-compose.production.yml   ← port 80, memory limits, .env.production
```

Docker Compose merges them automatically:
```bash
# This is what the convenience scripts do:
docker compose -f docker-compose.yml -f docker-compose.staging.yml up -d --build
```

---

## Troubleshooting

### Check which environment is running
```bash
curl http://localhost:8080/api/       # Returns {"environment": "staging", ...}
curl http://localhost/api/            # Returns {"environment": "production", ...}
```

### Check if database is connected
```bash
curl http://localhost:8080/api/health  # Returns {"status": "healthy", "checks": {"database": "ok"}}
```

### View logs
```bash
# Docker
docker compose -f docker-compose.yml -f docker-compose.staging.yml logs backend --tail=100

# Systemd (if deployed with setup.sh)
sudo journalctl -u sipsense-api -f

# Filter JSON logs for errors (staging/production emit JSON)
docker compose logs backend | jq 'select(.level == "ERROR")'
```

### Roll back a bad deploy
```bash
git revert HEAD
git push origin main
# Staging auto-redeploys; manually trigger production deploy after verifying staging
```
