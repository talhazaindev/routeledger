# Test results

Recorded 2026-10-02 during local verification. Do not invent results.

## Backend (`pytest`)

```text
cd backend && USE_FAKE_PROVIDER=true pytest
.......................                                                  [100%]
23 passed
```

Includes golden fixture, HOS boundary cases, DST unsupported, fuel gaps, validator mutations, and API create/get/auth/quota with the fake provider.

## Frontend unit (`vitest`)

```text
cd frontend && npm test
Test Files  1 passed (1)
Tests  1 passed (1)
```

## Playwright

```text
cd frontend && npm run test:e2e
5 passed
```

- Short preset → map + daily log
- Layout screenshots at 375 / 768 / 1024 / 1440 (`frontend/e2e/screenshots/`)

## Production build

```text
cd frontend && npm run build
✓ built successfully
```

## Live ORS smoke

**Passed 2026-10-02** with HeiGIT key configured:

- Geocode via `https://api.heigit.org/pelias/v1/autocomplete`
- Directions via `https://api.heigit.org/openrouteservice/v2/directions/driving-hgv/json` (`driving-hgv`)
- Full `POST /api/trips/` Chicago → Joliet → Bloomington returned `Within modeled limits` with provider `openrouteservice-heigit`

Note: HeiGIT `/geojson` directions path currently returns 406; adapter uses `/json` and decodes the polyline.

## Hosted production smoke

**Not run** — GitHub token invalid; Vercel/Render CLIs absent. Deployment config is present (`Dockerfile`, `docker-compose.yml`, `render.yaml`, `frontend/vercel.json`).
