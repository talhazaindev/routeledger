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

Deploy the **frontend on Vercel** and the **API on Render**. Do not deploy the repo root to Vercel — the root `Dockerfile` is for the Django API and will crash there (wrong port / no DB).

### 1. Backend (Render)

[`render.yaml`](render.yaml) defines a web service (`backend/`) and PostgreSQL database.

1. Create a new Render Blueprint from this repo (or connect the repo and use `render.yaml`).
2. In the Render dashboard, set:
   - `OPENROUTESERVICE_API_KEY`
   - `DJANGO_ALLOWED_HOSTS` — your Render hostname (e.g. `routeledger-api.onrender.com`)
   - `CORS_ALLOWED_ORIGINS` / `CSRF_TRUSTED_ORIGINS` — your Vercel origin (e.g. `https://routeledger-six.vercel.app`)
3. Note the public API URL (e.g. `https://routeledger-api.onrender.com`).

### 2. Frontend (Vercel)

1. Import the repo in Vercel.
2. Set **Root Directory** to `frontend` (Framework Preset: Vite).
3. Build command: `npm run build` · Output: `dist`.
4. In [`frontend/vercel.json`](frontend/vercel.json), replace `REPLACE_WITH_RENDER_HOST` with your Render hostname (no trailing slash), then redeploy. Example:

   ```json
   "destination": "https://routeledger-api.onrender.com/api/$1"
   ```

API calls from the UI (`/api/...`) are proxied to Render via that rewrite.

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
