# RouteLedger

US trucking trip planner that builds FMCSA-style daily logs from a route, pickup/dropoff, cycle hours, and departure time. The React UI shows the map, itinerary, directions, and printable/PDF log sheets; the Django API persists immutable trip plans and handles geocoding and routing.

## Stack

| Layer    | Tech |
| -------- | ---- |
| Frontend | React 19, Vite, Tailwind CSS, Leaflet, TanStack Query |
| Backend  | Django 5, Django REST Framework, drf-spectacular |
| Routing  | OpenRouteService / HeiGIT (optional fake provider for local dev) |
| Database | SQLite locally when `DATABASE_URL` is unset; PostgreSQL in production |

## Prerequisites

- Python 3.12+
- Node.js 20+ (for the frontend)
- An [HeiGIT / OpenRouteService API key](https://account.heigit.org/) for real routes (or use fake geometry locally)

## Quick start (local)

1. **Environment**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` as needed. For UI-only development without an ORS key, set `USE_FAKE_PROVIDER=true`.

2. **Backend**

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r backend/requirements.txt
   cd backend
   python manage.py migrate
   python manage.py runserver
   ```

   API: `http://127.0.0.1:8000`  
   OpenAPI schema: `/api/schema/` · Swagger UI: `/api/docs/`

3. **Frontend** (separate terminal)

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

   App: `http://127.0.0.1:5173` (Vite proxies `/api` to the backend)

## Docker Compose (API + PostgreSQL)

Runs the API with Postgres and fake routing by default:

```bash
docker compose up --build
```

API on port `8000`. Set `OPENROUTESERVICE_API_KEY` in your shell or `.env` if you want real ORS calls inside Compose.

## Environment variables

See [`.env.example`](.env.example) for the full list. Important entries:

- `OPENROUTESERVICE_API_KEY` — required for real geocoding/routing when `USE_FAKE_PROVIDER=false`
- `ORS_BASE_URL` / `ORS_GEOCODE_BASE_URL` — HeiGIT endpoints (defaults in `.env.example`)
- `DATABASE_URL` — PostgreSQL connection string (production); omit for SQLite
- `CORS_ALLOWED_ORIGINS` / `CSRF_TRUSTED_ORIGINS` — must include your frontend origin

## API overview

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/api/health/` | Health check |
| GET | `/api/locations/search/?q=` | Location autocomplete |
| POST | `/api/trips/` | Create trip plan |
| GET | `/api/trips/{id}/` | Load plan (Bearer access token) |

Detailed contract: [`docs/openapi.yaml`](docs/openapi.yaml).

## Deployment

Deploy the **frontend on Vercel** and the **API** on a Django host (PythonAnywhere, Render, etc.). Do not run the Django Docker image as the Vercel frontend project.

### 1. Backend (PythonAnywhere / Render)

Current production API: `https://devdota.pythonanywhere.com`

Set on the API host:
- `OPENROUTESERVICE_API_KEY`
- `DJANGO_ALLOWED_HOSTS` — API hostname
- `CORS_ALLOWED_ORIGINS` / `CSRF_TRUSTED_ORIGINS` — Vercel origin (`https://routeledger-nine.vercel.app`)

[`render.yaml`](render.yaml) is an alternate Render Blueprint if you prefer that host.

### 2. Frontend (Vercel)

Root [`vercel.json`](vercel.json) builds `frontend/` and proxies `/api/*` to the Django host:

```json
"destination": "https://devdota.pythonanywhere.com/api/$1"
```

Production UI: `https://routeledger-nine.vercel.app`

## Project layout

```
RouteLedger/
├── backend/          # Django project (trips domain, API, ORS client)
├── frontend/         # Vite React app
├── docs/             # OpenAPI spec
├── docker-compose.yml
├── backend/Dockerfile  # API image
└── .env.example
```

## License

Proprietary unless otherwise noted in repository metadata.
