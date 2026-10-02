# RouteLedger Assumptions

## Assessment-supplied

- Property-carrying driver
- 70 hours / 8 days cycle
- No adverse driving conditions
- Fuel at least every 1,000 miles
- Pickup and dropoff each require one hour on-duty (not driving)

## Explicit product assumptions

- **Fresh shift at departure:** at least ten hours off duty before the planned departure; driving since qualifying break = zero. The four mandatory inputs do not encode shift state.
- **Conservative cycle estimate:** the scalar “Current Cycle Used” is carried forward until a 34-hour restart. Unknown prior daily history is not fabricated. This may schedule more rest than a full history would require.
- **Rest status:** defaults to OFF. Sleeper berth (SB) only when the user selects equipped sleeper and planned sleeper use. No split-sleeper scheduling.
- **Fuel stop duration:** default 30 minutes (application assumption, not a regulatory requirement).
- **Miles since fuel:** default 0 (full tank); editable in [0, 1000].
- **Pre-trip inspection:** optional 15 minutes ON, OFF by default.
- **Home-terminal timezone:** default `America/Chicago`, user-selected; all log times use this zone.
- **Departure:** default next calendar day at 08:00 in the home-terminal zone.
- **Single driver:** daily driving miles and total vehicle miles may match under this assumption.
- **HGV routing:** profile `driving-hgv` only. Unspecified vehicle dimensions and incomplete map restrictions mean truck suitability is not guaranteed.
- **Planned stops:** baseline rest/fuel pins are “Planned rest area along route — facility not verified.” No invented business names.
- **DST:** trips whose home-terminal days are not exactly 24 hours are unsupported; change departure instead of compressing a sheet.

## Not claimed

- Not a certified ELD, vehicle telemetry product, or official record of completed driving.
- Generated pages are labeled: “Planned driver log — not a certified ELD record.”
- Never invent signatures or completed activity.
- Do not say “DOT approved,” “certified,” or unconditional “legally compliant.”
- Valid plans may show “Within modeled limits” only after independent validation.

## Cycle recap

- Unknown history columns display “History required,” not zero.
- 60-hour / 7-day recap area is marked not applicable for this product.

## Provider limits (HeiGIT Standard, verified)

- Directions: 2,000/day, 40/minute
- Geocoding: 3,000/day, 100/minute
- Max driving distance: 6,000 km per request
- Base URL: `https://api.heigit.org/openrouteservice`
