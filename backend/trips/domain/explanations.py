"""Deterministic explanations for timeline events."""

from __future__ import annotations

from .types import EventType, ReasonCode, TimelineEvent


def explain_event(event: TimelineEvent) -> str:
    """Return a grounded 'Why this stop?' explanation from reason codes and clocks."""
    codes = set(event.reason_codes)
    clocks = event.clocks_at_end
    parts: list[str] = []

    if event.event_type == EventType.PICKUP:
        parts.append(
            f"Pickup requires one hour on-duty (not driving). "
            f"Cycle used after this stop: {_fmt_h(clocks.cycle_used_s)}."
        )
        if event.duration_s >= 1800 and event.clocks_at_start.driving_since_break_s >= 8 * 3600:
            parts.append("This pickup also satisfies the 30-minute driving interruption.")
        elif event.duration_s >= 1800:
            parts.append("This on-duty hour counts toward a qualifying 30-minute interruption.")
    elif event.event_type == EventType.DROPOFF:
        parts.append(
            f"Dropoff requires one hour on-duty (not driving). "
            f"Trip service completes at the end of this hour."
        )
    elif event.event_type == EventType.FUEL:
        parts.append(
            "Fuel stop inserted so driving does not exceed 1,000 miles since last fuel. "
            "Location is a planned point along the route — facility not verified."
        )
        if event.duration_s >= 1800:
            parts.append("A 30-minute fuel stop also satisfies the driving interruption requirement.")
    elif event.event_type == EventType.BREAK:
        parts.append(
            "A qualifying interruption of at least 30 consecutive minutes non-driving "
            "is required after 8 hours of driving."
        )
    elif event.event_type == EventType.REST:
        if ReasonCode.SPLIT_SLEEPER_LONG in codes:
            parts.append(
                "Split sleeper: at least 7 consecutive hours in the sleeper berth "
                "(§395.1(g)). This period is excluded from the 14-hour window when "
                "paired with a later qualifying rest of at least 2 hours."
            )
            parts.append("A new 11/14 calculation period begins after this sleeper period.")
        elif ReasonCode.SPLIT_SLEEPER_SHORT in codes:
            parts.append(
                "Split sleeper companion rest completes the §395.1(g) pair "
                "(periods total at least 10 hours). Both paired periods are excluded "
                "from the 14-hour driving window."
            )
        else:
            if ReasonCode.SHIFT_DRIVING_LIMIT in codes:
                parts.append(
                    "Driving stopped after reaching the 11-hour driving limit. "
                    "A qualifying 10-hour rest starts a new shift."
                )
            if ReasonCode.SHIFT_WINDOW_LIMIT in codes:
                parts.append(
                    "Driving stopped because the 14-hour window from the first on-duty "
                    "activity expired. Short breaks do not pause this window."
                )
            if ReasonCode.BREAK_AFTER_DRIVING in codes and ReasonCode.SHIFT_DRIVING_LIMIT not in codes:
                parts.append("Rest also resets the 8-hour driving interruption clock.")
            if not parts:
                parts.append("A qualifying 10-hour rest is required before more driving.")
            parts.append("Ten hours of rest does not reset the 70-hour/8-day cycle.")
    elif event.event_type == EventType.RESTART:
        parts.append(
            "A 34-hour restart is required because cycle driving availability is exhausted "
            "(conservative cycle estimate). Continuous off-duty time is extended to 34 hours "
            "total rather than adding an extra 34 hours after a prior 10-hour rest."
        )
        parts.append("After this restart, cycle used returns to zero.")
    elif event.event_type == EventType.INSPECTION:
        parts.append(
            "Optional 15-minute pre-trip inspection (on-duty not driving), enabled in planning settings."
        )
    elif event.event_type == EventType.DRIVING:
        if ReasonCode.SHIFT_DRIVING_LIMIT in codes:
            parts.append("Driving segment ends at the 11-hour shift driving limit.")
        elif ReasonCode.SHIFT_WINDOW_LIMIT in codes:
            parts.append("Driving segment ends at the 14-hour window limit.")
        elif ReasonCode.BREAK_AFTER_DRIVING in codes:
            parts.append("Driving segment ends after 8 hours without a 30-minute interruption.")
        elif ReasonCode.CYCLE_LIMIT in codes:
            parts.append("Driving segment ends because the 70-hour cycle allowance is exhausted.")
        else:
            parts.append("Driving along the planned road route.")
    else:
        parts.append(event.event_type.value.replace("_", " ").title())

    return " ".join(parts)


def _fmt_h(seconds: int) -> str:
    hours = seconds / 3600
    if abs(hours - round(hours)) < 1e-9:
        return f"{int(round(hours))}h"
    return f"{hours:.2f}h"
