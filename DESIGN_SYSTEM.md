# RouteLedger Design System

## Character

Precise, calm, trustworthy dispatch software. Working tool, not a marketing landing page. No oversized heroes, stock trucking photos, purple gradients, glassmorphism, or decorative animations.

## Tokens

| Token | Value | Use |
| --- | --- | --- |
| background | `#F5F7FA` | App chrome |
| surface | `#FFFFFF` | Panels, cards |
| text | `#14263D` | Primary copy |
| text-muted | `#526174` | Secondary |
| border | `#DCE3EC` | Dividers, inputs |
| action | `#0F766E` | Primary buttons |
| duty-off | slate `#64748B` | Off duty |
| duty-sb | violet `#7C3AED` | Sleeper berth |
| duty-d | blue `#2563EB` | Driving |
| duty-on | amber `#D97706` | On duty not driving |

Duty statuses always combine color with labels/icons/patterns. Print logs use a high-contrast dark status trace.

## Typography

- Self-hosted Inter with system sans fallback
- Tabular numerals for times and mileage
- Base body 14–16px
- Spacing scale: 4 / 8 px
- Radii: 10–14px
- Shadows: subtle elevation only

## Layout (desktop ~1440px)

- Compact header: wordmark, Planner, Logs, help
- Left panel ~360px: numbered inputs, cycle, settings, generate, presets
- Main: summary strip, dominant map, tabs (Itinerary / Directions / Daily logs / Plan insights)

## Mobile

Single-column form, then Overview / Map / Logs. Intentional map height. No whole-page horizontal overflow.

## Accessibility

WCAG 2.2 AA targets: contrast, semantic headings, field-associated errors, `aria-live` status, visible focus, accessible comboboxes, keyboard operation, reduced motion, 44px touch targets, textual timeline alternative to the map.

## Log sheets

Crisp SVG recreation of `assets/blank-paper-log.png`. Never stretch the PNG. Signature area blank. Planned-record banner on every sheet.
