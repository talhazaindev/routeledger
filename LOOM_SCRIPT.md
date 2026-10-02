# Loom walkthrough script (3–5 minutes)

Do not claim a recording exists until one is created.

## Recording checklist

- [ ] Backend running with real ORS key (preferred) or clearly labeled `USE_FAKE_PROVIDER`
- [ ] Frontend at the demo URL
- [ ] Short preset, multi-day or near-cycle preset ready
- [ ] Browser zoom 100%, desktop width ~1440
- [ ] Hide personal bookmarks/passwords
- [ ] PDF download works once before recording

## Demo presets

1. **Short route** — Chicago → Joliet → Bloomington, cycle 0  
2. **Near-exhausted cycle** — Chicago → Indianapolis, cycle 68  
3. **Multi-day** — Chicago → Kansas City → Denver  

## Script

### 0:00–0:25 — Problem and assumptions

“RouteLedger plans a US property-carrying trip and produces planned daily driver logs. Inputs are current, pickup, dropoff, and current cycle hours. We assume 70/8, fuel every thousand miles, one-hour pickup and dropoff, and a fresh shift. This is a planning simulator — not a certified ELD.”

### 0:25–1:15 — Real trip, map, stops

Click **Short route**, then **Generate trip plan**. Show map fit-bounds, markers, summary strip (distance, driving, completion). Open Itinerary; expand **Why this stop?** on pickup.

### 1:15–2:05 — Cycle / long-trip rest

Load **Near-exhausted cycle** (or multi-day). Generate. Point at restart/rest events and explain Conservative cycle estimate: the scalar total is carried until a 34-hour restart; we do not invent daily history.

### 2:05–2:45 — Daily log and PDF

Open **Daily logs**. Show midnight grid, four status rows, totals, remarks, blank signature, planned-record banner. Click **Download all logs PDF** (distinct from Print). Briefly open the PDF.

### 2:45–3:45 — Code and tests

Show `backend/trips/domain/scheduler.py` as pure Python. Mention golden fixture and independent validator. Flash pytest/Vitest results from `docs/TEST_RESULTS.md`.

### 3:45–4:30 — Deployment and limits

Mention Django on Render, React on Vercel, HeiGIT quotas, contiguous US only, DST unsupported days, planned stops not verified facilities. State real hosted URL if deployed; otherwise say “deployment config is ready; publish blocked on credentials.”

### Optional AI slot

Only if enabled and working — skip for baseline.
