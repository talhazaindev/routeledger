# RouteLedger

Assessment-quality US trucking trip planner with planned daily driver log sheets.

**Django 5.2.17 + React 19 + Vite + PostgreSQL/SQLite.** Generates a routed map, fuel/rest stops, itinerary, and SVG/PDF daily logs from current → pickup → dropoff and current cycle used hours.

> Planned driver log — not a certified ELD record.

## Supported scope

- Property-carrying driver, **70 hours / 8 days**
- Contiguous United States only
- Fresh shift at departure; **Conservative cycle estimate** (scalar cycle total carried until a 34-hour restart)
- Fuel at least every 1,000 miles (default stop 30 minutes)
- Pickup and dropoff each 1 hour on-duty
- Home-terminal timezone for all log axes (default `America/Chicago`)
- DST transition days in the home-terminal zone are **unsupported** (change departure)
- HGV routing via OpenRouteService `driving-hgv` (truck suitability not guaranteed)

See [ASSUMPTIONS.md](ASSUMPTIONS.md), [ARCHITECTURE.md](ARCHITECTURE.md), [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md).

## Required keys

| Variable | Where to obtain |
| --- | --- |
| `OPENROUTESERVICE_API_KEY` | [HeiGIT account](https://account.heigit.org/) — free Standard plan |
| `ORS_BASE_URL` | Must be `https://api.heigit.org/openrouteservice` |

**Verified Standard quotas (2026):** Directions 2,000/day · 40/min; Geocoding 3,000/day · 100/min; max driving distance 6,000 km.

For local UI work without a key, set `USE_FAKE_PROVIDER=true` (approximate geometry labeled as fake).

## Local setup

```bash
# Python 3.12
cd RouteLedger
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
# Edit .env — set USE_FAKE_PROVIDER=true or add OPENROUTESERVICE_API_KEY

cd backend
python manage.py migrate
python manage.py runserver 8000
```

```bash
# Frontend (second terminal)
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173 — Vite proxies `/api` to Django.

### Docker (optional)

```bash
docker compose up --build
```

## Tests

```bash
# Backend
source .venv/bin/activate
cd backend && USE_FAKE_PROVIDER=true pytest

# Frontend unit
cd frontend && npm test

# Playwright (starts API + Vite if needed)
cd frontend && npx playwright install chromium
cd frontend && npm run test:e2e
```

## Production build

```bash
cd frontend && npm run build
cd backend && DJANGO_DEBUG=false python manage.py check --deploy
```

## Deployment

Preferred: **Vercel** (frontend) + **Render** (Django) + managed PostgreSQL.

1. Create a HeiGIT API key.
2. Deploy backend with `render.yaml` (or equivalent). Set `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`, `OPENROUTESERVICE_API_KEY`, `USE_FAKE_PROVIDER=false`, `DJANGO_DEBUG=false`.
3. Deploy `frontend/` to Vercel. Update `frontend/vercel.json` rewrite destination to the Render API host.
4. Confirm `/api/health/` through the frontend domain, create a trip, open logs, download PDF.

**Cold start:** Render free web services sleep. Expect ~30–60s for the first request after idle; use an always-on tier for assessment day if available.

**Hosting status:** Live production URLs are not claimed in this repository until accounts and keys are authorized. Remaining blockers: ORS key, GitHub auth, Vercel/Render login.

## AI configuration

`AI_INSIGHTS_ENABLED=false` by default. Baseline uses deterministic “Why this stop?” explanations only. Optional LLM explainer is deferred.

## API

- `GET /api/health/`
- `GET /api/locations/search/?q=`
- `POST /api/trips/`
- `GET /api/trips/{id}/` with `Authorization: Bearer <token>`
- OpenAPI: `/api/schema/` · Swagger: `/api/docs/`

## Loom walkthrough

See [LOOM_SCRIPT.md](LOOM_SCRIPT.md). Do not invent a Loom URL unless a recording exists.
