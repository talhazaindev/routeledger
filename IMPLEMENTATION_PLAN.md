# Implementation Plan & Requirements Checklist

## Milestones

| ID | Milestone | Status |
| --- | --- | --- |
| A | Domain foundation | In progress |
| B | Real vertical slice | Pending |
| C | Long-trip correctness + PDF | Pending |
| D | Design polish | Pending |
| E | Delivery assets | Pending |
| F | Optional AI | Deferred (`AI_INSIGHTS_ENABLED=false`) |

## Requirements → tests / screens

| Requirement | Verification |
| --- | --- |
| Short trip, 1h pickup/dropoff | `test_short_trip_golden` |
| 8h drive then pickup satisfies break | `test_pickup_satisfies_break` |
| 8h at arrival: no redundant break | `test_arrival_at_eight_hours` |
| 11h driving boundary | `test_eleven_hour_limit` |
| 14h window | `test_fourteen_hour_window` |
| Cycle 69 at pickup | `test_cycle_69_pickup` |
| Cycle 70 no drive until restart | `test_cycle_70` |
| 10h rest does not reset cycle; 34h does | `test_restart_vs_daily_rest` |
| 2500 mi fuel intervals ≤1000 | `test_fuel_2500_miles` |
| Fuel 30 / 15 / adjacent break | `test_fuel_break_qualification` |
| Midnight splits | `test_midnight_split` |
| Full rest day sheet | `test_restart_rest_day` |
| Exact midnight completion | `test_exact_midnight_no_extra_page` |
| Zero-length legs, invalid bounds | `test_identical_locations`, API validation |
| Terminal TZ across borders | `test_terminal_timezone` |
| DST unsupported | `test_dst_unsupported` |
| Lon/lat + progress interpolation | `test_progress_index` |
| Event invariants | validator + mutation tests |
| 24h pages; padding excluded from trip | `test_daily_page_totals` |
| Keyboard / stale search / sync | Vitest + Playwright |
| PDF page count & totals | Playwright PDF test |
| Golden fixture 08:00→15:00 | `test_golden_fixture` |

## Progress notes

- 2026-10-02: Scaffold Django 5.2.17 + docs; paper log present at `assets/blank-paper-log.png`.
- 2026-10-02: Domain engine + golden fixture + validator (23 pytest).
- 2026-10-02: API slice with fake provider, bearer trip access.
- 2026-10-02: Full planner UI, SVG logs, PDF export, Playwright 5/5 at required widths.
- ORS key unset; live provider smoke deferred.
- GitHub/Vercel/Render auth blocked for publish.

## Milestone status

| ID | Milestone | Status |
| --- | --- | --- |
| A | Domain foundation | Complete |
| B | Real vertical slice | Complete |
| C | Long-trip correctness + PDF | Complete |
| D | Design polish | Complete (screenshots in frontend/e2e/screenshots) |
| E | Delivery assets | Complete (hosting publish blocked on credentials) |
| F | Optional AI | Deferred (`AI_INSIGHTS_ENABLED=false`) |
