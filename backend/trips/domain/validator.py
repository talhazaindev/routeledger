"""Independent timeline invariant validator.

Recalculates clocks from the event stream. Does not trust the scheduler's flag.
"""

from __future__ import annotations

from .constants import (
    BREAK_DRIVING_LIMIT_S,
    BREAK_REQUIRED_S,
    CYCLE_LIMIT_S,
    CYCLE_RESTART_S,
    DAILY_REST_S,
    FUEL_INTERVAL_M,
    SHIFT_DRIVING_LIMIT_S,
    SHIFT_WINDOW_LIMIT_S,
)
from .types import (
    DutyStatus,
    EventType,
    PlanningSettings,
    ReasonCode,
    TimelineEvent,
    ValidationResult,
)


def validate_timeline(
    events: tuple[TimelineEvent, ...] | list[TimelineEvent],
    settings: PlanningSettings | None = None,
) -> ValidationResult:
    """Walk events and detect corrupted schedules."""
    errors: list[str] = []
    warnings: list[str] = []

    if not events:
        return ValidationResult(ok=False, errors=("timeline is empty",))

    # Contiguity and positive durations
    prev_end = events[0].start_utc
    for i, ev in enumerate(events):
        if ev.duration_s <= 0 and ev.event_type != EventType.MARKER:
            errors.append(f"event {ev.event_id} has non-positive duration {ev.duration_s}")
        if ev.end_utc < ev.start_utc:
            errors.append(f"event {ev.event_id} ends before it starts")
        actual = int((ev.end_utc - ev.start_utc).total_seconds())
        if actual != ev.duration_s:
            errors.append(
                f"event {ev.event_id} duration_s={ev.duration_s} != wall {actual}"
            )
        if i > 0 and ev.start_utc != prev_end:
            gap = int((ev.start_utc - prev_end).total_seconds())
            if gap > 0:
                errors.append(f"gap of {gap}s before event {ev.event_id}")
            elif gap < 0:
                errors.append(f"overlap of {-gap}s at event {ev.event_id}")
        prev_end = ev.end_utc

    # Required pickup / dropoff
    types = {e.event_type for e in events}
    if EventType.PICKUP not in types:
        errors.append("missing PICKUP event")
    if EventType.DROPOFF not in types:
        errors.append("missing DROPOFF event")

    # Replay clocks
    cycle_used = settings.cycle_used_s if settings else 0
    cycle_mode = "conservative_estimate"
    cycle_buckets: list[int] = [cycle_used]
    cycle_bucket_date = None
    tz_name = settings.home_terminal_tz if settings else "UTC"
    if settings and settings.cycle_daily_history_s is not None:
        cycle_mode = "rolling_history"
        cycle_buckets = list(settings.cycle_daily_history_s)
        cycle_used = sum(cycle_buckets)

    shift_driving = 0
    shift_elapsed = 0
    driving_since_break = 0
    miles_since_fuel = settings.miles_since_fuel_m if settings else 0
    continuous_rest = DAILY_REST_S
    window_open = False
    non_driving_streak = 0
    max_miles_since_fuel = miles_since_fuel

    def _roll_to_day(day) -> None:
        nonlocal cycle_used, cycle_bucket_date, cycle_buckets
        if cycle_mode != "rolling_history":
            return
        from datetime import timedelta

        if cycle_bucket_date is None:
            cycle_bucket_date = day
            return
        while cycle_bucket_date < day:
            cycle_bucket_date = cycle_bucket_date + timedelta(days=1)
            cycle_buckets.append(0)
            while len(cycle_buckets) > 8:
                cycle_buckets.pop(0)
            cycle_used = sum(cycle_buckets)

    def _add_cycle(duration_s: int, start_utc) -> None:
        nonlocal cycle_used
        if cycle_mode != "rolling_history" or settings is None:
            cycle_used += duration_s
            return
        from datetime import time as time_cls, timedelta
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(tz_name)
        remaining = duration_s
        cursor = start_utc
        while remaining > 0:
            local = cursor.astimezone(tz)
            day = local.date()
            _roll_to_day(day)
            next_midnight_local = __import__("datetime").datetime.combine(
                day + timedelta(days=1), time_cls.min, tzinfo=tz
            )
            next_midnight_utc = next_midnight_local.astimezone(start_utc.tzinfo)
            until = max(0, int((next_midnight_utc - cursor).total_seconds()))
            chunk = min(remaining, until if until > 0 else remaining)
            cycle_buckets[-1] += chunk
            remaining -= chunk
            cursor = cursor + timedelta(seconds=chunk)
        cycle_used = sum(cycle_buckets)

    if settings is not None:
        cycle_bucket_date = settings.departure_local.astimezone(
            __import__("zoneinfo").ZoneInfo(tz_name)
        ).date()

    for ev in events:
        if ev.status == DutyStatus.D:
            # Check limits before applying (the drive itself should not exceed)
            if shift_driving + ev.duration_s > SHIFT_DRIVING_LIMIT_S + 1:
                errors.append(
                    f"driving exceeds 11h limit at {ev.event_id}: "
                    f"{shift_driving + ev.duration_s}s"
                )
            if window_open and shift_elapsed + ev.duration_s > SHIFT_WINDOW_LIMIT_S + 1:
                errors.append(
                    f"driving exceeds 14h window at {ev.event_id}: "
                    f"{shift_elapsed + ev.duration_s}s"
                )
            if driving_since_break + ev.duration_s > BREAK_DRIVING_LIMIT_S + 1:
                errors.append(
                    f"driving exceeds 8h without break at {ev.event_id}: "
                    f"{driving_since_break + ev.duration_s}s"
                )
            if cycle_used + ev.duration_s > CYCLE_LIMIT_S + 1:
                errors.append(
                    f"driving exceeds 70h cycle at {ev.event_id}: "
                    f"{cycle_used + ev.duration_s}s"
                )

            if not window_open:
                window_open = True
                shift_elapsed = 0
                shift_driving = 0
                driving_since_break = 0

            shift_driving += ev.duration_s
            driving_since_break += ev.duration_s
            _add_cycle(ev.duration_s, ev.start_utc)
            miles_since_fuel += ev.distance_m
            max_miles_since_fuel = max(max_miles_since_fuel, miles_since_fuel)
            shift_elapsed += ev.duration_s
            continuous_rest = 0
            non_driving_streak = 0

        elif ev.status == DutyStatus.ON:
            if not window_open:
                window_open = True
                shift_elapsed = 0
                # ON work can start a window; driving clocks stay 0
            _add_cycle(ev.duration_s, ev.start_utc)
            shift_elapsed += ev.duration_s
            continuous_rest = 0
            non_driving_streak += ev.duration_s
            if non_driving_streak >= BREAK_REQUIRED_S:
                driving_since_break = 0
            if ev.event_type == EventType.FUEL:
                # Fuel resets after the stop; during the preceding drive we already counted
                miles_since_fuel = 0

        elif ev.status in (DutyStatus.OFF, DutyStatus.SB):
            non_driving_streak += ev.duration_s
            continuous_rest += ev.duration_s
            if non_driving_streak >= BREAK_REQUIRED_S:
                driving_since_break = 0
            exclude_window = ReasonCode.SPLIT_SLEEPER_LONG in ev.reason_codes or (
                ReasonCode.SPLIT_SLEEPER_SHORT in ev.reason_codes
            )
            if continuous_rest >= CYCLE_RESTART_S or (
                ev.event_type == EventType.RESTART and continuous_rest >= CYCLE_RESTART_S - 1
            ):
                cycle_used = 0
                cycle_buckets = [0]
                shift_driving = 0
                shift_elapsed = 0
                driving_since_break = 0
                window_open = False
            elif continuous_rest >= DAILY_REST_S or ev.duration_s >= DAILY_REST_S:
                # 10h rest resets shift, not cycle
                if ev.duration_s >= DAILY_REST_S or continuous_rest >= DAILY_REST_S:
                    shift_driving = 0
                    shift_elapsed = 0
                    driving_since_break = 0
                    window_open = False
            elif exclude_window:
                # Split sleeper periods excluded from 14h; calculation restarts after
                shift_driving = 0
                shift_elapsed = 0
                driving_since_break = 0
                window_open = False
            elif window_open:
                shift_elapsed += ev.duration_s

        # Fuel gap check across driving: peak miles since fuel must stay <= 1000
        # (reset happens at fuel events)

    # Post-pass: ensure no drive segment pushed fuel over limit mid-route
    fuel_m = settings.miles_since_fuel_m if settings else 0
    for i, ev in enumerate(events):
        if ev.status == DutyStatus.D:
            if fuel_m + ev.distance_m > FUEL_INTERVAL_M + 1:
                later_drive = any(e.status == DutyStatus.D for e in events[i + 1 :])
                if later_drive or fuel_m + ev.distance_m > FUEL_INTERVAL_M + 1609:
                    errors.append(
                        f"fuel interval exceeded at {ev.event_id}: "
                        f"{fuel_m + ev.distance_m}m > {FUEL_INTERVAL_M}m"
                    )
            fuel_m += ev.distance_m
            # Independent 8h break check using replayed driving_since_break
            # (already checked above during replay)
        elif ev.event_type == EventType.FUEL:
            fuel_m = 0

    # Detect 10h rest incorrectly clearing cycle
    for ev in events:
        if ReasonCode_CYCLE_CLEARED_FALSELY(ev):
            errors.append(f"10h rest appears to reset cycle at {ev.event_id}")

    # Detect unbroken 8h+ driving stretches via a clean replay of break clock
    break_clock = 0
    for ev in events:
        if ev.status == DutyStatus.D:
            break_clock += ev.duration_s
            if break_clock > BREAK_DRIVING_LIMIT_S + 1:
                errors.append(
                    f"break clock exceeded 8h at {ev.event_id} ({break_clock}s)"
                )
        else:
            # Non-driving of sufficient consecutive length resets
            # For mutation tests we also flag any single drive event > 8h
            if ev.duration_s >= BREAK_REQUIRED_S:
                break_clock = 0
            elif ev.status != DutyStatus.D:
                # accumulate partial — simplified: only full qualifying resets
                pass

    # Any single driving event longer than 8h without being split is invalid
    # when clocks claim break was already due
    for ev in events:
        if ev.status == DutyStatus.D and ev.duration_s > BREAK_DRIVING_LIMIT_S + 1:
            errors.append(
                f"single driving event exceeds 8h break limit at {ev.event_id}"
            )
        if (
            ev.status == DutyStatus.D
            and ev.clocks_at_start.driving_since_break_s + ev.duration_s
            > BREAK_DRIVING_LIMIT_S + 1
        ):
            errors.append(
                f"driving_since_break over 8h at {ev.event_id}"
            )

    ok = len(errors) == 0
    return ValidationResult(ok=ok, errors=tuple(errors), warnings=tuple(warnings))


def ReasonCode_CYCLE_CLEARED_FALSELY(ev: TimelineEvent) -> bool:
    """Heuristic: REST that zeroes cycle without being long enough for restart."""
    if ev.event_type != EventType.REST:
        return False
    start_cycle = ev.clocks_at_start.cycle_used_s
    end_cycle = ev.clocks_at_end.cycle_used_s
    if end_cycle == 0 and start_cycle > 0 and ev.duration_s < CYCLE_RESTART_S:
        # Unless continuous rest already nearly 34h
        if ev.clocks_at_start.continuous_rest_s + ev.duration_s < CYCLE_RESTART_S:
            return True
    return False


def mutate_for_tests(events: list[TimelineEvent], kind: str) -> list[TimelineEvent]:
    """Deliberately corrupt a timeline for validator tests."""
    from dataclasses import replace
    from datetime import timedelta

    if not events:
        return events
    out = list(events)
    if kind == "excessive_driving":
        for i, ev in enumerate(out):
            if ev.status == DutyStatus.D:
                out[i] = replace(
                    ev,
                    end_utc=ev.start_utc + timedelta(hours=12),
                    duration_s=12 * 3600,
                )
                break
    elif kind == "overlap":
        if len(out) >= 2:
            out[1] = replace(out[1], start_utc=out[0].start_utc)
    elif kind == "wrong_break_reset":
        for i, ev in enumerate(out):
            if ev.status == DutyStatus.D:
                out[i] = replace(
                    ev,
                    end_utc=ev.start_utc + timedelta(hours=9),
                    duration_s=9 * 3600,
                )
                break
    elif kind == "cycle_violation":
        for i, ev in enumerate(out):
            if ev.status == DutyStatus.D:
                from .types import ClockSnapshot

                bad_start = ClockSnapshot(
                    shift_driving_s=0,
                    shift_elapsed_s=0,
                    driving_since_break_s=0,
                    cycle_used_s=CYCLE_LIMIT_S,
                    miles_since_fuel_m=0,
                    continuous_rest_s=0,
                )
                out[i] = replace(
                    ev,
                    clocks_at_start=bad_start,
                    duration_s=3600,
                    end_utc=ev.start_utc + timedelta(hours=1),
                )
                break
    return out
