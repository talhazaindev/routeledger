# RouteLedger Architecture

## Scope

One Django application, one React SPA, one database. No microservices, message buses, Kubernetes, or background-task infrastructure.

## Layers

```
frontend (Vite/React)  →  /api proxy  →  Django REST
                                          ├─ api (views, serializers)
                                          ├─ services (orchestration)
                                          ├─ providers (OpenRouteService adapter)
                                          └─ domain (pure Python scheduler)
```

### Domain (`backend/trips/domain`)

Pure Python. No Django, HTTP, database, or AI imports.

- `types.py` — dataclasses for legs, events, clocks, settings
- `progress.py` — monotonic distance/time progress index over route geometry
- `scheduler.py` — deterministic HOS timeline builder
- `validator.py` — independent invariant checker
- `logs.py` — terminal-day log projection
- `explanations.py` — deterministic “Why this stop?” text
- `constants.py` — HOS limits in integer seconds

### Providers (`backend/trips/providers`)

- `base.py` — `RoutingProvider` protocol
- `openrouteservice.py` — HeiGIT `api.heigit.org` client (`driving-hgv`)
- `fake.py` — deterministic fixtures for tests and labeled demo mode

### Services (`backend/trips/services`)

Orchestrate: validate input → geocode/search → route two legs → schedule → validate → persist snapshot.

### API (`backend/trips/api`)

Thin DRF views. Consistent error envelope. Bearer token on trip reads.

## Data flow

1. Client posts trip input with resolved coordinates.
2. Service fetches `current→pickup` and `pickup→dropoff` road legs.
3. Domain scheduler emits a canonical event timeline.
4. Independent validator recalculates clocks; plan is rejected if invalid.
5. Log projection splits days in home-terminal timezone.
6. Immutable `TripPlan` snapshot is stored; raw access token returned once.

## Persistence

`TripPlan` holds UUID, created-at, canonical input JSON, route snapshot, timeline, daily logs, validation summary, rule version, provider metadata, and hashed access token. Modifying inputs creates a new plan.

## Time

All log axes use the selected home-terminal timezone. Instants are UTC with offsets in API timestamps. DST transition days (≠ 86,400 s) are rejected as unsupported.

## Frontend

Feature folders: `planner`, `map`, `itinerary`, `logs`. Shared UI under `components/ui`. The client never recomputes HOS clocks.
