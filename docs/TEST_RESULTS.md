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

**Not run** — `OPENROUTESERVICE_API_KEY` unset. Use HeiGIT key and `USE_FAKE_PROVIDER=false` before assessment demo.

## Hosted production smoke

**Not run** — GitHub token invalid; Vercel/Render CLIs absent. Deployment config is present (`Dockerfile`, `docker-compose.yml`, `render.yaml`, `frontend/vercel.json`).
