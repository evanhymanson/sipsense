# SipSense

AI-powered whiskey discovery app. Rate, review, and explore whiskeys with ML recommendations and an AI chat agent. Live at **sipsense.ai**.

---

## Tech Stack

- **Backend:** FastAPI, SQLAlchemy 2.0, PostgreSQL 16 (prod) / SQLite (dev), Gunicorn
- **Frontend:** React 19, Vite 7, React Router v7, Leaflet (maps)
- **ML/AI:** PyTorch NCF recommender, LangGraph + Claude chat agent, Claude API (tasting notes, pairings, flavor analysis)
- **Infra:** Docker Compose, GitHub Actions CI/CD, AWS EC2, nginx (SSL), S3 (image storage), Sentry (error tracking)

## Project Structure

```
backend/
  app/
    main.py              # FastAPI app, middleware, router registration
    models.py            # SQLAlchemy ORM (30+ tables)
    schemas.py           # Pydantic v2 request/response models
    database.py          # DB setup, auto-migration, indexing
    auth.py              # JWT auth (HS256 + bcrypt)
    routers/             # 30+ API routers (116+ endpoints)
    ml/
      collaborative_filter.py  # NCF PyTorch model
      recommender.py           # Content-based fallback (cosine similarity)
      agent.py                 # LangGraph chat agent with tools
      model.pt                 # Trained model weights
  tests/                 # pytest suite (20+ test files)

frontend/
  src/
    App.jsx              # Router, auth state, layout
    App.css              # Single global stylesheet (all styles here)
    api/client.js        # Centralized API client (JWT, dedup, retry)
    pages/               # 15 lazy-loaded pages
    components/          # 27+ reusable components
    utils/               # Helpers (stars, analytics)

.github/workflows/
  ci.yml                 # Tests + lint + build on PRs
  deploy.yml             # Auto-deploy to EC2 on merge to main
```

## Local Development

```bash
# Full stack via Docker
docker compose -f docker-compose.yml -f docker-compose.production.yml up --build

# Backend only (for development)
cd backend && pip install -r requirements.txt
SIPSENSE_ENV=development python -m uvicorn app.main:app --reload

# Frontend only (for development)
cd frontend && npm install && npm run dev
```

## Testing

```bash
# Backend (pytest, 50% coverage minimum)
cd backend && python -m pytest tests/ -v --cov=app --cov-fail-under=50

# Frontend (vitest + eslint)
cd frontend && npm test && npm run lint
```

CI runs both on every PR and push to main.

## Key Patterns

- API routes prefixed with `/api` — frontend client adds this automatically
- JWT auth via Bearer tokens stored in localStorage (`sipsense_token`)
- Pydantic v2 schemas validate all request/response data
- SQLAlchemy 2.0 ORM with auto-migration for new columns in `database.py`
- React pages are lazy-loaded via `React.lazy()` + `Suspense`
- All CSS lives in `App.css` — no CSS-in-JS, no CSS modules
- API client (`api/client.js`) deduplicates concurrent GET requests and handles token refresh
- Sentry integrated on both frontend and backend for error tracking
- Rate limiting: 300 requests/60s per IP

## Database

- **Production:** PostgreSQL 16 in Docker with persistent volume
- **Development:** SQLite with WAL mode (auto-detected)
- **Migrations:** Alembic + custom auto-migration in `database.py` that adds missing columns/indexes on startup
- **Key tables:** users, whiskeys, user_ratings (check-ins), follows, toasts, checkin_comments, collection_items, videos, journeys, badges, analytics_events

---

## Git Workflow (MUST FOLLOW)

**Never commit directly to `main`.** All work goes through feature branches and pull requests.

### For every task:
1. **Create a feature branch** before making any changes:
   ```
   git checkout main && git pull
   git checkout -b feature/<short-description>
   ```
2. **Do the work** — make commits on the feature branch
3. **Push and open a PR**:
   ```
   git push -u origin feature/<short-description>
   gh pr create --title "..." --body "..."
   ```
4. **User reviews and merges** the PR on GitHub
5. **After merge**, switch back to main:
   ```
   git checkout main && git pull
   ```

### Branch naming:
- Features: `feature/<name>` (e.g. `feature/onboarding-redesign`)
- Fixes: `fix/<name>` (e.g. `fix/deploy-secrets`)
- Chores: `chore/<name>` (e.g. `chore/cleanup-env-files`)

### Deploy flow:
- Merging to `main` auto-deploys to **production** (CI tests must pass first)
- Can also manually trigger production deploy via GitHub Actions workflow dispatch
