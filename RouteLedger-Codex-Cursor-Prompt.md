# RouteLedger — complete Codex / Cursor implementation prompt

Copy everything between BEGIN PROMPT and END PROMPT into your coding agent. Attach `blank-paper-log.png` to the coding session or put it in `docs/reference/blank-paper-log.png`. This prompt requests implementation, not just a proposal. Optional AI is deliberately feature-flagged pending product approval.

## BEGIN PROMPT

You are the lead full-stack engineer, solutions architect, and product designer responsible for delivering RouteLedger, an assessment-quality US trucking trip planner with daily driver log sheets. Build the working application, test it, polish it, and prepare the deployment and submission assets. Work through the milestones below; do not stop after scaffolding or a plan.

### 1. Objective and priorities

The assessment requires Django + React, a hosted application, GitHub source, and a 3–5 minute Loom walkthrough. Users enter current location, pickup location, dropoff location, and current cycle used in hours. The application returns a routed map, route instructions, fuel/rest stops, and completed daily log sheets for every day of the trip.

Assumptions explicitly supplied by the assessment: property-carrying driver; 70 hours / 8 days; no adverse driving conditions; fueling at least every 1,000 miles; pickup and dropoff each require one hour.

Priority order: correct scheduling and logs; complete real end-to-end flow; excellent usability and visual execution; reliable hosting; optional enhancements. This is a planning simulator generating prospective logs, not a certified ELD, vehicle telemetry product, or official record of completed driving. Label generated pages “Planned driver log — not a certified ELD record.” Never invent signatures or completed activity.

Keep the architecture small: one Django application, one React application, one database. No microservices, Kafka, Kubernetes, agent orchestration, vector database, or background task infrastructure without a demonstrated need. No authentication wall for the assessor, billing screens, fleet-management filler, or fake dashboard statistics.

### 2. Start with discovery and execution artifacts

Inspect the repository, its instructions, available skills, existing dependencies, and the reference image before editing. Preserve unrelated work. If the image is missing, continue with the specified log structure and report the missing reference.

Create `IMPLEMENTATION_PLAN.md`, `ARCHITECTURE.md`, `ASSUMPTIONS.md`, and `DESIGN_SYSTEM.md`. Record decisions briefly and keep implementation moving. Establish a requirements checklist mapped to actual tests and screens. Keep durable progress notes for long sessions.

Verify package compatibility against current official documentation; pin compatible stable versions and commit lockfiles. Do not use experimental versions just because they are newer. Preferred baseline: supported Python 3.12/3.13, Django 5.2 LTS at the current security patch, Django REST Framework, React + TypeScript + Vite, Tailwind CSS, shadcn/ui, Lucide, TanStack Query, React Hook Form + Zod, React Leaflet + Leaflet, and PostgreSQL. Use Python zoneinfo and a maintained frontend timezone library. Verify React Leaflet peer compatibility. SQLite is acceptable for quick local work only; production data must persist outside ephemeral app storage.

Use available frontend-design or UI UX Pro Max skills where compatible. Primary references:
- https://github.com/nextlevelbuilder/ui-ux-pro-max-skill
- https://github.com/anthropics/skills/tree/main/skills/frontend-design
- https://ui.shadcn.com/docs

Read current installation instructions and skill content before using third-party code. Prefer project-local tooling and a recorded version. Do not blindly execute remote shell scripts. If skills are unavailable, follow the concrete design requirements below. Skills are aids; screenshot inspection and working interactions determine acceptance.

### 3. Product flow and inputs

The default route `/` is the planner itself. Provide four prominent required inputs:
1. Current location.
2. Pickup location.
3. Dropoff location.
4. Current Cycle Used (Hrs), decimal input from 0 through 70 inclusive.

Explain cycle input inline: “Total on-duty time already used in your current 8-day cycle, including driving.” Accept finite numeric values only; reject empty, negative, NaN, infinity, and over-70 values on the server. Parse decimal hours precisely into integer seconds; do not accumulate floating-point hours.

Locations use accessible searchable comboboxes with city/state/country disambiguation. Persist the chosen display label and coordinates, not just typed text. Changing selected text invalidates coordinates until resolved again. Cancel obsolete searches and prevent stale responses from replacing newer results. Restrict supported routes to the contiguous United States; show a clear message for unsupported countries or unreachable road routes. Do not silently pick the first Springfield.

Below the four inputs, show a concise assumptions summary and an expandable “Planning settings” section:
- Departure date and time, default next day at 08:00 in the selected home-terminal zone, visibly editable before planning.
- Home-terminal timezone, default America/Chicago, visibly selected rather than inferred from the browser. Explain that all log times use this zone.
- Start with a fresh shift after at least ten hours off duty; driving since qualifying break = zero. This is an explicit assumption because the four mandatory inputs do not encode current shift state.
- Start with a full tank / zero miles since last fuel, editable as miles since fuel in [0, 1000].
- Fuel stop duration: default 30 minutes, an application assumption, not a regulatory requirement.
- Optional 15-minute pre-trip inspection, OFF by default to avoid silently adding unspecified assessment time; when enabled, on-duty not driving and included in all clocks.
- Rest status defaults to OFF. Only use SB when the user explicitly selects an equipped sleeper berth and planned sleeper use. No split-sleeper scheduling.
- Optional driver, carrier, main office, home terminal, tractor/trailer, co-driver, shipping document, shipper/commodity, and starting odometer fields. Unknown fields remain blank or “Not provided”; demo identities appear only in labeled demo data.

Make sample trips one-click form presets, not fabricated output. Include a short route, a multi-day route, and a near-exhausted-cycle route. Presets run the real backend. Offline fixtures belong only to clearly labeled demo mode and tests.

### 4. Routing, mapping, and location services

Use openrouteservice as the primary hosted routing/geocoding provider, subject to current account quotas and endpoint availability. Prefer `driving-hgv`; do not silently substitute car routing. Explain that unspecified vehicle dimensions and incomplete map restrictions prevent a guarantee of truck suitability. Keep its key server-side. Use a provider adapter so it can be replaced. Verify the actual free account limits at setup rather than promising unlimited requests.

Map rendering, routing, and geocoding are separate services. Use Leaflet with configurable OSM-compatible tiles. For modest demo traffic, standard OSM tiles can be used only with visible attribution, valid Referer, normal browser caching, no bulk downloads, and no offline prefetch. Support changing tile provider through configuration. Do not rely on public OSRM demo servers as a production backend. Do not implement autocomplete against public Nominatim; its policy forbids it. Use an autocomplete-capable provider endpoint, or explicit search on submit if the configured provider lacks autocomplete.

Fetch current→pickup and pickup→dropoff road legs with route geometry, distance, travel duration, and instructions. Zero-length identical-location legs must work; pickup and dropoff activities still occur. Respect provider distance/waypoint limits; route the two legs separately when appropriate. Reject unsupported lengths clearly rather than replacing the road route with straight lines.

Normalize GeoJSON [longitude, latitude] at the API boundary and convert explicitly to Leaflet [latitude, longitude]. Keep meters and seconds internally; convert to miles for display. Preserve provider provenance, profile, fetched time, and route version. Treat ETA as an estimate without live traffic unless live traffic actually exists.

Create a monotonic progress index across routing steps: cumulative distance, cumulative estimated driving duration, geometry offsets, and coordinates. Locate driving-limit stops by time progress and fuel stops by distance progress. Use step durations where supplied and proportional interpolation within a step, documenting the approximation. Never interpolate by polyline vertex count or straight-line start/end coordinates. Cross-midnight daily miles use this same progress model.

Distinguish a planned stop location along the route from a verified fuel station or legal truck parking facility. Baseline pins may represent a “Planned rest area along route — facility not verified”; do not invent business names or imply stopping on a highway is safe. Where actual POIs are supported, choose a reachable candidate before the limit, reroute to include the detour, and recalculate all clocks and fuel mileage. Otherwise keep the limitation visible. POI verification is an enhancement and must not derail baseline delivery.

Server requests need bounded timeouts, bounded retries for transient errors, Retry-After handling, caching, and quota protection. Cache by normalized inputs plus provider/profile/options/version; cache geocoding separately. Never cache secrets or send them to the browser. A routing failure must retain the form and show retry/change-location actions. Map tiles failing must not hide an already calculated itinerary or logs.

### 5. Deterministic scheduling domain

Build a pure Python scheduling engine independent of Django, network calls, UI, database, and AI. Its inputs are normalized route legs, settings, and initial driver state; outputs are typed timeline events plus diagnostics. All downstream representations must derive from that canonical timeline. Use integer seconds, timezone-aware instants, and half-open intervals [start, end). Reject negative or zero-duration events except separately modeled instantaneous markers.

Before implementation, verify rules against these primary references:
- https://www.fmcsa.dot.gov/regulations/hours-service/summary-hours-service-regulations
- https://www.ecfr.gov/current/title-49/subtitle-B/chapter-III/subchapter-B/part-395/subpart-A/section-395.3
- https://www.ecfr.gov/current/title-49/subtitle-B/chapter-III/subchapter-B/part-395/subpart-A/section-395.8

Implement these supported rules:
- No more than 11 hours of driving in a shift following a qualifying 10-hour rest.
- No driving beyond the 14-hour elapsed window beginning with the first on-duty activity after qualifying rest. Ordinary short breaks do not pause it.
- After 8 cumulative hours driving without 30 consecutive minutes non-driving, take a qualifying interruption before more driving. Adjacent non-driving statuses may jointly qualify. Pickup, dropoff, and a sufficiently long fuel stop can qualify; do not insert a duplicate break.
- D and ON count toward cycle usage. OFF and SB do not.
- Do not drive after the applicable 70-hour/8-day limit. Ten hours of rest does not reset this cycle; a qualifying 34-hour restart does.
- Pickup and dropoff each consume exactly 3,600 seconds ON, including when they share a location. Fuel is ON. Rest is OFF or explicitly selected SB.
- The 14-hour and cycle rules restrict driving; do not falsely describe them as an absolute legal prohibition on additional non-driving work. The planner may complete a one-hour service event after driving availability expires, then prohibit further driving until eligible. Display exhausted cycle availability as zero, with actual accumulated duty preserved.

Cycle history is a critical modeling constraint. A scalar Current Cycle Used cannot reveal which hours roll out on future days. Baseline mode must be explicitly named “Conservative cycle estimate”: carry the unknown initial total forward until a 34-hour restart and do not fabricate daily history or promise the earliest possible arrival. Also retain generated duty until restart in this conservative mode. This may schedule more rest than necessary; explain why. Full history mode is optional: it requires the previous seven daily on-duty totals, today's prior duty, a consistent departure state, and restart information sufficient for the supported model. Validate totals and implement terminal-day rollover correctly if offered. Do not add an unfinished history toggle. Unknown recap columns must say “History required,” not zero.

At each step, compute remaining driving allowance from shift driving, elapsed shift window, break requirement, and cycle availability. Advance only to the earliest applicable event: route-leg end, duty limit, break limit, fuel threshold, and history rollover if supported. Handle simultaneous boundaries in one deterministic decision, avoid duplicate rests, and guarantee forward progress.

Prefer combining required events when valid: a 30-minute fueling event satisfies the driving interruption; a 10-hour rest satisfies it too; a 34-hour restart also satisfies the daily rest requirement. If already continuously off duty for ten hours and a restart is needed, extend the continuous rest to 34 total, not an extra 34. Never count ON fueling as part of ten or 34 consecutive hours off duty.

Track miles since last fuel across both legs, all driving shifts, calendar boundaries, and detours. Insert fuel before exceeding 1,000 miles; do not reset fuel at pickup or midnight. Arriving at the final destination at exactly 1,000 miles does not require a redundant post-trip fuel stop. If any subsequent driving would exceed the threshold, fuel first. Enforce custom initial miles-since-fuel. Bound total planning horizon/event count with an actionable unsupported-trip response rather than an infinite loop.

Every event carries a stable ID; type; OFF/SB/D/ON status; UTC start/end; duration; start/end route progress; distance; coordinates where applicable; location label and its provenance; reason codes; clock snapshots; and leg reference. Useful reasons include PICKUP, DROPOFF, FUEL_INTERVAL, BREAK_AFTER_DRIVING, SHIFT_DRIVING_LIMIT, SHIFT_WINDOW_LIMIT, CYCLE_RESTART, and INSPECTION. Do not merge event semantics away even if chart intervals share the same status.

Implement a separate invariant validator that walks the resulting event stream and recalculates clocks. It must catch corrupted schedules, not merely echo the scheduler's validity flag. Only show “Within modeled limits” after validation, together with the assumptions. Never use “DOT approved,” “certified,” or unconditional “legally compliant.”

### 6. Time handling and daily log sheets

Use one home-terminal time basis for every sheet; crossing state/timezone borders never resets clocks or switches log axes. Preserve UTC internally and include offsets in API timestamps. Do not use the assessor's browser timezone for dates or page boundaries.

Daylight-saving transitions require explicit behavior. Implement and test an evidence-backed transition-day representation before claiming support. If that is outside the assessment scope, detect trips crossing a home-terminal UTC-offset transition and return an explicit unsupported-date message with an option to change departure. Do not silently squeeze 23/25 elapsed hours into a normal 24-hour sheet. Document this bounded limitation.

Generate every terminal-calendar day touched by the trip, including full rest days during restart. Split display intervals at day boundaries without resetting shift, break, cycle, or fuel state. Do not generate an empty next-day sheet when completion is exactly midnight. Fill time before departure and after completion with clearly marked assumed OFF duty; these planning fillers must not change trip completion, trip rest metrics, or unknown prior-cycle history. Ordinary supported pages total exactly 86,400 seconds.

Use the supplied `blank-paper-log.png` as the visual and field reference. Recreate it in crisp SVG rather than stretching a low-resolution image. Include:
- Date and from/to locations.
- Daily driving miles and total vehicle miles; in the single-driver assumption these may match, with that assumption documented.
- Carrier, main office, terminal, truck/trailer, driver/co-driver, shipping reference, and commodity fields when supplied.
- Midnight-to-midnight grid; clear hourly labels including Noon and Midnight; quarter-hour minor divisions.
- Four labeled rows in reference order: Off Duty, Sleeper Berth, Driving, On Duty (not driving).
- Horizontal status segments with vertical connectors at the precise transition time. Do not use diagonal connections or generic bar charts in place of the graph.
- Each status total at the right, displayed to sufficient precision for the totals to reconcile. A zero SB row remains visible.
- Remarks with transition time, city/state when available, and activity. Unknown or estimated locations are explicitly marked. Keep long remarks on a numbered continuation page if necessary.
- 70-hour/8-day recap with exact generated values only where supportable. Label unknown history fields. Keep the template's alternative 60-hour/7-day area visibly not applicable or omit it from the faithful modern recreation with explanation.
- Signature area left blank, planned-record label, and page numbering.

The display has quarter-hour guides, but do not round actual events to 15-minute intervals. Use exact time coordinates and deterministic formatting. Daily miles summed across pages must equal trip miles within a declared display-rounding tolerance; rounding must not alter engine calculations.

Build one reusable React SVG log component consumed by both the daily preview and a dedicated print view. Provide a real “Download all logs PDF” action using a verified SVG-capable PDF path, plus browser print as fallback. A “Print” button must not masquerade as a direct PDF download. Preserve searchable text/vector lines when possible. Paginate to US Letter, one daily sheet per page plus clearly associated remarks continuations. Keep fonts embedded or self-hosted. Test a many-day export visually; no cropped right-hand totals, overlapping remarks, blank pages, missing fonts, or chart-only exports.

### 7. UI and UX direction

Brand: RouteLedger. Product character: precise, calm, trustworthy dispatch software with strong information hierarchy. Design a working tool, not a marketing landing page. Avoid oversized hero sections, decorative trucking stock photos, purple gradients, glassmorphism, excessive cards, and unnecessary animations.

Use a light workspace with dark navy text and header, restrained teal actions, neutral borders, and semantic duty colors. Suggested starting tokens: background #F5F7FA, surface #FFFFFF, primary text #14263D, secondary text #526174, border #DCE3EC, primary action #0F766E. Adjust any token failing contrast. Driving blue, ON amber, OFF slate, SB violet; distinguish with labels/icons/patterns, never color alone. Print the reference log with a high-contrast dark trace.

Use a readable self-hosted sans font such as Inter with system fallback; tabular numerals for time/mileage. Base text around 14–16px, comfortable labels, a consistent 4/8px spacing scale, 10–14px radii, subtle shadows only where elevation helps. Minimum readable chart labels; large map controls and touch targets. Use Lucide SVG icons with accessible button labels.

Desktop composition at ~1440px:
- Compact header: wordmark, Planner, Logs when available, and unobtrusive assumptions/help access.
- Left panel ~340–380px: numbered route inputs linked visually in travel order, cycle input with remaining-hours text, expandable settings, primary “Generate trip plan,” and sample presets.
- Main area: concise summary strip above a dominant map; distance, driving time, total elapsed trip time, completion date/time, and log-day count. Show arrival at dropoff separately from completion after unloading.
- Beneath or alongside the map: accessible tabs for Itinerary, Directions, Daily logs, and optional Plan insights. Avoid three cramped sidebars.
- A compact limits summary shows remaining clocks at the selected event, explicitly labeled as planned values rather than live telemetry.

Interaction requirements:
- Clicking a map stop selects its itinerary event and corresponding log day. Selecting an itinerary event highlights/pans to its map position. Selecting a day filters or highlights that day's route segments.
- Day-grouped itinerary with exact start/end, duration, location, distance, duty label, and “Why this stop?” explanation.
- Numbered start/pickup/dropoff markers; distinct rest/fuel markers; collocated events grouped into one expandable marker. Clear selected state and always-visible map legend/attribution.
- Route fit-bounds after successful calculation, not every render. Explicit fit-route control. Avoid annoying scroll zoom capture.
- Keyboard-accessible day navigation, previous/next controls, readable full-page log preview, zoom/fit controls, and export actions.
- Mobile: single-column form, then results with Overview/Map/Logs navigation; map gets an intentional height and logs get pan/zoom or a dedicated full-width view. No whole-page horizontal overflow.
- Keep input edits separate from the displayed plan; mark prior results “Inputs changed — regenerate” and disable stale export until recalculation or explicit restoration. Never relabel old results as the new trip.
- During calculation show truthful stages such as “Finding route” and “Building schedule” only when actually observable; otherwise use one honest loading indicator, not fake percent progress.
- Preserve input on errors. Provide empty, loading, success, no-route, quota-limited, network-failure, and export-failure states. Do not hide actionable errors only in transient toasts.
- No dead buttons, decorative filter chips, fake live statuses, invented user avatars, or nonfunctional settings.

Target WCAG 2.2 AA: contrast, semantic headings, field-associated validation, aria-live status messages, visible focus, accessible comboboxes/dialogs, keyboard operation, reduced motion, touch target sizing, and a textual route/timeline alternative to map interaction. Verify 375, 768, 1024, and 1440px widths, plus browser zoom at 200% and long place names.

### 8. Backend, API, and persistence

Suggested structure:
`backend/config`, `backend/trips/api`, `backend/trips/domain`, `backend/trips/providers`, `backend/trips/services`, `backend/tests`, `frontend/src/features/planner`, `frontend/src/features/map`, `frontend/src/features/itinerary`, `frontend/src/features/logs`, `frontend/src/components/ui`, `docs`.

Use typed domain records/dataclasses with small, descriptive functions. Keep Django views thin; serializers validate; services orchestrate; adapters fetch; the pure engine schedules; log projection splits days; validator checks invariants. Frontend components do not reimplement legal calculations.

API baseline:
- `GET /api/health/`: lightweight readiness with no secrets.
- `GET /api/locations/search/?q=...`: rate-limited location search.
- `POST /api/trips/`: validated input → route → schedule → independent validation → immutable persisted plan snapshot.
- `GET /api/trips/{id}/`: load authorized plan and all normalized results.
- Optional AI explanation endpoint only when enabled.

Return consistent JSON errors with code, message, field errors, retryability, and request ID. Define OpenAPI schema and frontend response types. Appropriate distinctions: validation 400; inaccessible trip 404; quota 429; upstream failure 502/503. Do not expose upstream stack traces or API tokens.

Persist TripPlan with UUID, creation timestamp, canonical input, normalized route, timeline/log projections or reproducible snapshot, rule version, provider metadata, settings, and validation summary. Modifying inputs creates a new snapshot. Define response schema versioning. Use an anonymous session or explicit unguessable read token for access, not public enumeration; UUID alone is not an authorization policy. Share links are optional and explicit. Prefer same-origin `/api` proxying for frontend/backend session simplicity; if using separate origins, test cookie/CORS/CSRF configuration in the actual deployment.

Add payload-size limits, reasonable route/event limits, request throttling, strict coordinate bounds, frontend/backend input validation, and fixed provider base URLs. Do not accept arbitrary URLs for the server to fetch. Secrets belong in environment variables and `.env.example` contains placeholders only. Logs must redact secrets and avoid unnecessary address/driver information. Use HTTPS, production DEBUG=false, specific ALLOWED_HOSTS and trusted origins, and Django deployment checks.

### 9. Optional AI: grounded “Explain this plan”

Build deterministic “Why this stop?” explanations first, with reason codes and exact clock values. This feature works without an LLM.

Keep any LLM enhancement behind `AI_INSIGHTS_ENABLED=false` by default until approved. The useful optional feature is a small contextual plan explainer, not a general chatbot. It may answer “Why is this restart needed?”, “Why did arrival move to tomorrow?”, and “What changed between these two computed plans?”

The server gives the model only sanitized relevant plan facts and a small versioned rule summary with source URLs. Do not send driver identities or exact addresses unnecessarily. Output uses a validated schema with summary, referenced event IDs, rule IDs, and assumptions. Validate references and numerical claims against canonical data; fail back to deterministic explanations if validation fails. Restrict response length and request cost; apply timeouts, throttling, caching, and model configuration through environment variables. Protect against instruction text embedded in location names or remarks.

The model never calculates HOS, edits logs, invents fuel stations, creates route geometry, or determines validity. For a what-if question, require structured input confirmation, invoke the deterministic planner, then explain the resulting difference. No hidden mutation of the current plan. No vector database or multi-agent framework is necessary. Missing credentials or AI downtime must have zero effect on core assessment functionality. Label deterministic explanations honestly; do not call them AI-generated.

### 10. Verification that matters

Use pytest + pytest-django for domain/API tests, property-based tests where useful, Vitest/React Testing Library for critical UI behavior, and Playwright for browser acceptance and screenshots. Fixtures must be deterministic and not depend on live geocoding. Keep live provider smoke checks separate from CI.

Required tests:
1. Short trip: correct two legs, one-hour pickup/dropoff, no unnecessary rest, one day when appropriate.
2. Eight driving hours followed immediately by a one-hour pickup: pickup satisfies interruption; no redundant break before the next drive.
3. Exactly eight driving hours at final arrival: do not add a break solely to finish unloading.
4. Eleven-hour driving boundary: no additional driving before qualifying rest.
5. Fourteen-hour window expires with driving allowance left: driving still stops; short OFF periods do not extend the window.
6. Initial cycle 69 hours with current=pickup: pickup can consume the remaining hour; no subsequent drive before restart in conservative mode.
7. Initial cycle 70 hours: no driving until restart. ON work is handled without a false assertion that the rule forbids all work.
8. Ten-hour rest does not reset cycle; extending continuous rest to 34 hours resets it once.
9. A 2,500-mile route includes sufficient fuel so every between-fuel/final-driving gap is ≤1,000 miles; fuel does not reset at pickup or midnight.
10. Fuel of 30 minutes satisfies interruption; fuel of 15 minutes alone does not; adjacent ON/OFF interruption totaling 30 does.
11. Midnight during drive/rest/service: pages split, event semantics and clocks remain continuous, daily mileage reconciles.
12. Full rest day in a 34-hour restart produces an appropriate sheet.
13. Exact-midnight completion does not produce an empty extra page.
14. Identical locations, zero-length legs, fractional cycle input, invalid bounds, no route, provider timeout/429, and long supported trips.
15. Crossing geographic timezones keeps terminal time. Offset-transition dates follow the documented supported/unsupported policy.
16. Route longitude/latitude conversion and distance/time interpolation on unevenly sampled geometry.
17. All events have positive durations, ordered contiguous coverage, no overlap, no omitted pickup/dropoff, and no future drive beyond limits.
18. Every ordinary daily page has exactly 24 hours of statuses. Trip duration excludes padding before/after the trip.
19. Keyboard form completion, stale search response cancellation, accessible errors, changing inputs after success, synchronized map/day selection, and mobile layout.
20. PDF is real and has correct page count, readable fields and graph, complete remarks, and totals matching screen/API.

Add at least one hand-calculated golden fixture independently of implementation:
Departure 08:00, fresh shift, cycle zero, no inspection; leg one 2 hours/100 miles; pickup 1 hour; leg two 3 hours/150 miles; dropoff 1 hour. Finish 15:00; trip driving 5h, ON 2h, elapsed 7h, driving distance 250mi. On that day's completed planning sheet OFF = 17h, SB = 0h, D = 5h, ON = 2h. No fuel or break is needed with fresh fuel. Verify all representations against these exact expectations.

Deliberately mutate otherwise-valid fixture timelines and ensure the independent validator detects excessive driving, wrong break reset, overlap, and cycle violations. Do not call tests passed without running them. Document any tests unavailable due to environment constraints.

Use Playwright to inspect actual screenshots at required widths and a multi-day print export. Fix clipping, cramped typography, legend overlap, bad keyboard focus, and unreadable chart totals. Inspect the console and network requests. Run clean production builds and a fresh-clone setup check.

### 11. Hosting and operational delivery

Preferred deployment: React/Vite frontend on Vercel; Django on Render or an equivalent persistent Python host; managed PostgreSQL. Vercel is an option for the frontend, not a reason to replace Django with Next.js or serverless JavaScript. Verify current service tiers, sleep behavior, and costs; do not claim that every hosting component is free. A cold-starting backend is a demo risk: communicate the actual expected behavior and prefer an available reliable tier for assessment day.

Include Dockerfile, local compose setup if useful, `.env.example`, migrations, production start/build commands, static-file strategy, frontend SPA rewrites, backend health checks, and exact deployment steps. Test browser requests through the deployed frontend domain, not just curl against the backend. Verify direct-link reload, CSRF/session continuity, route generation, logs, and PDF export in production.

Use existing authorized hosting/GitHub access if available. If credentials or external account creation block publishing, finish code/configuration/tests and report the exact remaining action. Never invent a deployed URL, GitHub repository, Loom link, test result, or production status. No secrets or paid resources without authorization.

### 12. Milestones and completion

A. Domain foundation: typed route/events, documented assumptions, core scheduler, golden fixture and independent validator.
B. Real vertical slice: form → provider route → schedule → map/itinerary → one complete daily sheet.
C. Long-trip correctness: rest/fuel/cycle boundaries, multiple sheets, export, failure handling and persistence.
D. Design polish: final tokens, all interactive states, responsive/accessibility review, screenshot fixes.
E. Delivery: production builds, deployment configuration, real hosted smoke test where authorized, clear README, and walkthrough assets.
F. Optional approved AI enhancement only after A–E pass.

Required repository deliverables: working frontend/backend, tests, migrations/lockfiles, reference asset where permitted, README, ARCHITECTURE.md, ASSUMPTIONS.md, DESIGN_SYSTEM.md, API schema, deployment instructions, concise test results, and `LOOM_SCRIPT.md`.

The README must contain exact local setup, required keys and where to obtain them, supported scope, documented calculation assumptions, provider limitations, test commands, deployment steps, real URLs when available, and AI configuration if implemented.

Write a 3–5 minute Loom script with this approximate sequence: 0:00–0:25 problem and assumptions; 0:25–1:15 submit a real trip and show map/stops; 1:15–2:05 near-cycle-limit or long-trip example and rest explanation; 2:05–2:45 daily log/PDF; 2:45–3:45 code structure, deterministic engine and boundary tests; 3:45–4:30 deployment and supported limitations. AI may get a short slot only if working. Include recording checklist and demo presets. Do not claim to have recorded Loom unless an actual recording was created.

Before finishing, report what was built, verified test/build results, remaining limitations, setup/deployment blockers, and exact commands to run. A polished mock frontend with no genuine routing/scheduling, partial log sheets, or fake exports does not satisfy this task.

## END PROMPT

## Research notes for the project owner

Prepared 2 October 2026. The legal rules were cross-checked between FMCSA and 49 CFR 395.3/395.8. The design and engineering choices above are architectural recommendations, not claims that a particular framework is uniquely best or the newest. The linked YouTube video could not be retrieved; its captions were not used or claimed as evidence. The provided PNG was visually inspected.

Current primary references:
- FMCSA HOS summary: https://www.fmcsa.dot.gov/regulations/hours-service/summary-hours-service-regulations
- Driving limits and restart: https://www.ecfr.gov/current/title-49/subtitle-B/chapter-III/subchapter-B/part-395/subpart-A/section-395.3
- Log fields, duty rows, time basis and totals: https://www.ecfr.gov/current/title-49/subtitle-B/chapter-III/subchapter-B/part-395/subpart-A/section-395.8
- openrouteservice service overview: https://openrouteservice.org/services/
- Current account/plans: https://account.heigit.org/info/plans
- Routing restrictions: https://openrouteservice.org/restrictions/
- OSM tile policy: https://operations.osmfoundation.org/policies/tiles/
- Nominatim policy: https://operations.osmfoundation.org/policies/nominatim/
- Django 5.2 LTS: https://docs.djangoproject.com/en/5.2/releases/5.2/
- Django deployment checklist: https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
- shadcn/ui: https://ui.shadcn.com/docs
- UI UX Pro Max: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill
- Anthropic frontend-design: https://github.com/anthropics/skills/tree/main/skills/frontend-design
- Vercel Vite deployment: https://vercel.com/docs/frameworks/frontend/vite
- Render Django deployment: https://render.com/docs/deploy-django

Suggested AI product decision: approve grounded explanations and comparisons of already-computed plans first. Natural-language trip entry can follow, but adds location-disambiguation work. Autonomous scheduling, LLM-generated logs, and a generic trucking chatbot offer less value for this assessment than correct, explainable plans.
