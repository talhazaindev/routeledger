"""Deterministic HOS scheduler — pure Python, no I/O."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from .constants import (
    BREAK_DRIVING_LIMIT_S,
    BREAK_REQUIRED_S,
    CYCLE_LIMIT_S,
    CYCLE_RESTART_S,
    DAILY_REST_S,
    DROPOFF_DURATION_S,
    FUEL_INTERVAL_M,
    INSPECTION_DURATION_S,
    MAX_EVENTS,
    MAX_PLAN_DAYS,
    PICKUP_DURATION_S,
    SECONDS_PER_DAY,
    SHIFT_DRIVING_LIMIT_S,
    SHIFT_WINDOW_LIMIT_S,
)
from .explanations import explain_event
from .progress import ProgressIndex, build_progress_index
from .types import (
    ClockSnapshot,
    Coordinates,
    DriverState,
    DutyStatus,
    EventType,
    LocationProvenance,
    PlanningSettings,
    ReasonCode,
    RouteLeg,
    ScheduleResult,
    TimelineEvent,
)
from .validator import validate_timeline


def hours_to_seconds(hours: float | Decimal | str) -> int:
    """Parse decimal hours into integer seconds without float accumulation."""
    value = Decimal(str(hours))
    if not value.is_finite():
        raise ValueError("cycle hours must be finite")
    if value < 0 or value > 70:
        raise ValueError("cycle hours must be between 0 and 70 inclusive")
    return int((value * Decimal(3600)).to_integral_value(rounding=ROUND_HALF_UP))


def _new_id() -> str:
    return str(uuid4())


def _snapshot(state: DriverState) -> ClockSnapshot:
    return ClockSnapshot(
        shift_driving_s=state.shift_driving_s,
        shift_elapsed_s=state.shift_elapsed_s,
        driving_since_break_s=state.driving_since_break_s,
        cycle_used_s=state.cycle_used_s,
        miles_since_fuel_m=state.miles_since_fuel_m,
        continuous_rest_s=state.continuous_rest_s,
    )


def _day_length_s(tz: ZoneInfo, day) -> int:
    """Length of a terminal calendar day (detects DST 23h/25h days).

    Uses POSIX timestamps because subtracting two aware datetimes that share the
    same ZoneInfo instance ignores the mid-day offset change in CPython.
    """
    from datetime import date as date_cls, time as time_cls

    if not isinstance(day, date_cls):
        day = day.date()
    next_day = day + timedelta(days=1)
    start = datetime.combine(day, time_cls.min, tzinfo=tz)
    end = datetime.combine(next_day, time_cls.min, tzinfo=tz)
    return int(end.timestamp() - start.timestamp())


def _assert_no_dst_issues(tz_name: str, start_utc: datetime, end_utc: datetime) -> None:
    tz = ZoneInfo(tz_name)
    start_local = start_utc.astimezone(tz)
    end_local = end_utc.astimezone(tz)
    day = start_local.date()
    last = end_local.date()
    # Exact midnight end belongs to the previous day for sheet purposes,
    # but still reject if that previous day is a transition day.
    if (
        end_local.hour == 0
        and end_local.minute == 0
        and end_local.second == 0
        and end_local.microsecond == 0
        and end_local > start_local
    ):
        last = (end_local - timedelta(seconds=1)).date()
    while day <= last:
        if _day_length_s(tz, day) != SECONDS_PER_DAY:
            raise DstUnsupportedError(
                f"Trip touches a DST transition day ({day.isoformat()}) in {tz_name}. "
                "Change departure to avoid offset-transition dates."
            )
        day = day + timedelta(days=1)


class DstUnsupportedError(ValueError):
    code = "DST_TRANSITION_UNSUPPORTED"


class UnsupportedTripError(ValueError):
    code = "UNSUPPORTED_TRIP"


class SchedulerState:
    """Mutable working state during scheduling."""

    def __init__(self, initial: DriverState, now: datetime) -> None:
        self.cycle_used_s = initial.cycle_used_s
        self.shift_driving_s = initial.shift_driving_s
        self.shift_elapsed_s = initial.shift_elapsed_s
        self.driving_since_break_s = initial.driving_since_break_s
        self.miles_since_fuel_m = initial.miles_since_fuel_m
        self.continuous_rest_s = initial.continuous_rest_s
        self.shift_window_open = initial.shift_window_open
        self.shift_window_start: datetime | None = None
        self.now = now
        self.events: list[TimelineEvent] = []
        self.route_progress_m = 0
        self.non_driving_streak_s = 0  # consecutive non-driving for break qualification

    def as_driver(self) -> DriverState:
        return DriverState(
            cycle_used_s=self.cycle_used_s,
            shift_driving_s=self.shift_driving_s,
            shift_elapsed_s=self.shift_elapsed_s,
            driving_since_break_s=self.driving_since_break_s,
            miles_since_fuel_m=self.miles_since_fuel_m,
            continuous_rest_s=self.continuous_rest_s,
            shift_window_open=self.shift_window_open,
        )

    def remaining_cycle_driving_s(self) -> int:
        return max(0, CYCLE_LIMIT_S - self.cycle_used_s)

    def remaining_shift_driving_s(self) -> int:
        return max(0, SHIFT_DRIVING_LIMIT_S - self.shift_driving_s)

    def remaining_window_s(self) -> int:
        if not self.shift_window_open:
            return SHIFT_WINDOW_LIMIT_S
        return max(0, SHIFT_WINDOW_LIMIT_S - self.shift_elapsed_s)

    def remaining_before_break_s(self) -> int:
        return max(0, BREAK_DRIVING_LIMIT_S - self.driving_since_break_s)

    def remaining_fuel_m(self) -> int:
        return max(0, FUEL_INTERVAL_M - self.miles_since_fuel_m)

    def max_driving_s(self) -> int:
        return min(
            self.remaining_shift_driving_s(),
            self.remaining_window_s(),
            self.remaining_before_break_s(),
            self.remaining_cycle_driving_s(),
        )

    def open_window_if_needed(self) -> None:
        if not self.shift_window_open:
            self.shift_window_open = True
            self.shift_window_start = self.now
            self.shift_elapsed_s = 0
            self.shift_driving_s = 0
            self.driving_since_break_s = 0

    def apply_elapsed(self, duration_s: int) -> None:
        if self.shift_window_open:
            self.shift_elapsed_s += duration_s


def schedule_trip(
    legs: list[RouteLeg],
    settings: PlanningSettings,
    *,
    validate: bool = True,
) -> ScheduleResult:
    """Build a canonical timeline from normalized route legs and settings."""
    if settings.rest_status == DutyStatus.SB and not settings.sleeper_equipped:
        raise ValueError("Sleeper berth rest requires sleeper_equipped=True")
    if settings.miles_since_fuel_m < 0 or settings.miles_since_fuel_m > FUEL_INTERVAL_M:
        raise ValueError("miles_since_fuel_m must be in [0, 1000 miles]")
    if settings.cycle_used_s < 0 or settings.cycle_used_s > CYCLE_LIMIT_S:
        raise ValueError("cycle_used_s must be in [0, 70h]")

    departure = settings.departure_local
    if departure.tzinfo is None:
        raise ValueError("departure_local must be timezone-aware")
    tz = ZoneInfo(settings.home_terminal_tz)
    departure = departure.astimezone(tz)

    initial = DriverState(
        cycle_used_s=settings.cycle_used_s,
        miles_since_fuel_m=settings.miles_since_fuel_m,
        continuous_rest_s=DAILY_REST_S,
        fresh_shift=True,
        shift_window_open=False,
    )
    state = SchedulerState(initial, departure.astimezone(timezone.utc))
    progress = build_progress_index(legs)

    rest_status = (
        DutyStatus.SB
        if settings.sleeper_equipped and settings.rest_status == DutyStatus.SB
        else DutyStatus.OFF
    )

    # Optional pre-trip inspection
    if settings.include_pretrip_inspection:
        _emit_service(
            state,
            event_type=EventType.INSPECTION,
            status=DutyStatus.ON,
            duration_s=INSPECTION_DURATION_S,
            reasons=(ReasonCode.INSPECTION,),
            label=legs[0].from_label if legs else "Origin",
            coord=_coord_at(progress, 0),
            provenance=LocationProvenance.USER_SELECTED,
            leg_id=legs[0].leg_id if legs else None,
        )

    # Process each leg: drive then service at destination
    for i, leg in enumerate(legs):
        is_first = i == 0
        service_type = EventType.PICKUP if is_first else EventType.DROPOFF
        service_reason = ReasonCode.PICKUP if is_first else ReasonCode.DROPOFF
        service_duration = PICKUP_DURATION_S if is_first else DROPOFF_DURATION_S
        dest_label = leg.to_label
        dest_progress_end = state.route_progress_m + leg.distance_m

        remaining_leg_m = leg.distance_m
        remaining_leg_s = leg.duration_s

        while remaining_leg_m > 0 or remaining_leg_s > 0:
            if len(state.events) >= MAX_EVENTS:
                raise UnsupportedTripError(
                    "Trip exceeds maximum planned events; shorten the route or reduce cycle constraints."
                )
            horizon = state.now + timedelta(days=MAX_PLAN_DAYS)
            if state.now >= horizon:
                raise UnsupportedTripError(
                    "Trip exceeds maximum planning horizon of 21 days under conservative cycle rules."
                )

            drive_cap_s = state.max_driving_s()
            fuel_cap_m = state.remaining_fuel_m()

            # If no driving allowed, rest (or restart) before continuing
            if drive_cap_s <= 0:
                _insert_required_rest(state, settings, rest_status, progress)
                continue

            # Determine how far we can drive before the next boundary
            # Map fuel distance to estimated time using remaining leg proportion
            if remaining_leg_m <= 0:
                break

            # Time available limited by drive cap and remaining leg time
            # Distance available limited by fuel and remaining leg distance
            # Convert fuel meters to seconds via remaining leg ratio when possible
            if remaining_leg_s > 0 and remaining_leg_m > 0:
                speed_m_per_s = remaining_leg_m / remaining_leg_s
            else:
                speed_m_per_s = 0.0

            max_m_by_time = (
                int(drive_cap_s * speed_m_per_s) if speed_m_per_s > 0 else remaining_leg_m
            )
            drive_m = min(remaining_leg_m, fuel_cap_m, max_m_by_time if speed_m_per_s > 0 else remaining_leg_m)
            if speed_m_per_s > 0:
                drive_s = min(
                    remaining_leg_s,
                    drive_cap_s,
                    int(round(drive_m / speed_m_per_s)) if drive_m < remaining_leg_m else remaining_leg_s,
                )
            else:
                drive_s = 0

            # If fuel is the binding constraint and drive_m == fuel_cap, stop for fuel
            # after consuming up to fuel_cap (do not exceed)
            if drive_m <= 0 and fuel_cap_m <= 0:
                _emit_fuel(state, settings, progress, rest_status)
                continue
            if drive_s <= 0 and drive_cap_s > 0 and remaining_leg_m > 0:
                # Edge: tiny remainder — force rest if somehow stuck
                if state.max_driving_s() <= 0:
                    _insert_required_rest(state, settings, rest_status, progress)
                    continue
                # Drive a minimal remaining second if meters remain but time rounds to 0
                drive_s = min(1, remaining_leg_s) if remaining_leg_s > 0 else 0
                drive_m = min(remaining_leg_m, max(drive_m, 1))

            if drive_s <= 0 and remaining_leg_m <= 0:
                break
            if drive_s <= 0:
                _insert_required_rest(state, settings, rest_status, progress)
                continue

            # Clamp: if fuel would be exceeded by continuing after this segment,
            # stop at fuel threshold for intermediate fuel (not at exact final dest
            # when this finishes the whole remaining route with no further driving)
            hit_fuel = drive_m >= fuel_cap_m and fuel_cap_m < remaining_leg_m
            # Also if after this drive miles_since_fuel would hit interval and more driving remains later
            start_m = state.route_progress_m
            end_m = start_m + drive_m

            reasons: list[ReasonCode] = [ReasonCode.ROUTE_LEG]
            if drive_s >= drive_cap_s:
                if state.remaining_shift_driving_s() <= drive_s:
                    reasons.append(ReasonCode.SHIFT_DRIVING_LIMIT)
                if state.remaining_window_s() <= drive_s:
                    reasons.append(ReasonCode.SHIFT_WINDOW_LIMIT)
                if state.remaining_before_break_s() <= drive_s:
                    reasons.append(ReasonCode.BREAK_AFTER_DRIVING)
                if state.remaining_cycle_driving_s() <= drive_s:
                    reasons.append(ReasonCode.CYCLE_LIMIT)

            _emit_driving(
                state,
                duration_s=drive_s,
                distance_m=drive_m,
                start_m=start_m,
                end_m=end_m,
                progress=progress,
                leg_id=leg.leg_id,
                reasons=tuple(reasons),
            )
            remaining_leg_m -= drive_m
            remaining_leg_s = max(0, remaining_leg_s - drive_s)

            # Only interrupt mid-leg. Destination service (pickup/dropoff) runs
            # first after the leg ends and may satisfy the 30-minute break.
            more_on_this_leg = remaining_leg_m > 0
            more_driving_later = more_on_this_leg or any(
                l.distance_m > 0 for l in legs[i + 1 :]
            )
            if more_on_this_leg and (
                hit_fuel
                or state.miles_since_fuel_m >= FUEL_INTERVAL_M
            ):
                _emit_fuel(state, settings, progress, rest_status)
            elif more_on_this_leg and state.max_driving_s() <= 0:
                _insert_required_rest(state, settings, rest_status, progress)
            elif (
                not more_on_this_leg
                and state.miles_since_fuel_m >= FUEL_INTERVAL_M
                and more_driving_later
            ):
                # Fuel threshold reached exactly at a waypoint with more driving ahead
                pass  # service first; fuel before next leg is handled below

        # Arrive at destination — service event (may satisfy break)
        dest_coord = _coord_at(progress, dest_progress_end)
        state.route_progress_m = dest_progress_end
        _emit_service(
            state,
            event_type=service_type,
            status=DutyStatus.ON,
            duration_s=service_duration,
            reasons=(service_reason,),
            label=dest_label,
            coord=dest_coord,
            provenance=LocationProvenance.USER_SELECTED,
            leg_id=leg.leg_id,
        )

        # After service, fuel if needed before subsequent driving
        later_driving = any(l.distance_m > 0 for l in legs[i + 1 :])
        if later_driving and state.miles_since_fuel_m >= FUEL_INTERVAL_M:
            _emit_fuel(state, settings, progress, rest_status)
        if later_driving and state.max_driving_s() <= 0:
            _insert_required_rest(state, settings, rest_status, progress)

    # Ensure DST policy for the whole trip span
    if state.events:
        _assert_no_dst_issues(
            settings.home_terminal_tz,
            state.events[0].start_utc,
            state.events[-1].end_utc,
        )

    diagnostics: dict[str, Any] = {
        "cycle_mode": "conservative_estimate",
        "rule_version": "hos-property-carrying-70-8-v1",
        "total_driving_s": sum(
            e.duration_s for e in state.events if e.status == DutyStatus.D
        ),
        "total_on_s": sum(
            e.duration_s for e in state.events if e.status == DutyStatus.ON
        ),
        "total_distance_m": progress.total_m,
        "event_count": len(state.events),
        "completion_utc": state.events[-1].end_utc.isoformat() if state.events else None,
    }

    events = tuple(state.events)
    for i, ev in enumerate(events):
        events = (
            *events[:i],
            replace(ev, explanation=explain_event(ev)),
            *events[i + 1 :],
        )

    result = ScheduleResult(events=events, diagnostics=diagnostics)
    if validate:
        validation = validate_timeline(events, settings)
        result = ScheduleResult(
            events=events,
            diagnostics=diagnostics,
            validation=validation,
        )
    return result


def _coord_at(progress: ProgressIndex, meters: int) -> Coordinates | None:
    if not progress.points:
        return None
    return progress.coordinate_at_distance(meters)


def _emit_driving(
    state: SchedulerState,
    *,
    duration_s: int,
    distance_m: int,
    start_m: int,
    end_m: int,
    progress: ProgressIndex,
    leg_id: str,
    reasons: tuple[ReasonCode, ...],
) -> None:
    if duration_s <= 0:
        raise ValueError("driving duration must be positive")
    state.open_window_if_needed()
    start_clocks = _snapshot(state.as_driver())
    start = state.now
    end = start + timedelta(seconds=duration_s)

    state.shift_driving_s += duration_s
    state.driving_since_break_s += duration_s
    state.cycle_used_s += duration_s
    state.miles_since_fuel_m += distance_m
    state.apply_elapsed(duration_s)
    state.continuous_rest_s = 0
    state.non_driving_streak_s = 0
    state.route_progress_m = end_m
    state.now = end

    end_clocks = _snapshot(state.as_driver())
    start_c = _coord_at(progress, start_m)
    end_c = _coord_at(progress, end_m)
    ev = TimelineEvent(
        event_id=_new_id(),
        event_type=EventType.DRIVING,
        status=DutyStatus.D,
        start_utc=start,
        end_utc=end,
        duration_s=duration_s,
        reason_codes=reasons,
        clocks_at_start=start_clocks,
        clocks_at_end=end_clocks,
        start_progress_m=start_m,
        end_progress_m=end_m,
        distance_m=distance_m,
        start_coord=start_c,
        end_coord=end_c,
        location_label=None,
        location_provenance=LocationProvenance.ROUTE_INTERPOLATED,
        leg_id=leg_id,
    )
    state.events.append(ev)


def _emit_service(
    state: SchedulerState,
    *,
    event_type: EventType,
    status: DutyStatus,
    duration_s: int,
    reasons: tuple[ReasonCode, ...],
    label: str,
    coord: Coordinates | None,
    provenance: LocationProvenance,
    leg_id: str | None,
) -> None:
    if duration_s <= 0:
        raise ValueError("service duration must be positive")
    state.open_window_if_needed()
    start_clocks = _snapshot(state.as_driver())
    start = state.now
    end = start + timedelta(seconds=duration_s)

    if status in (DutyStatus.ON, DutyStatus.D):
        state.cycle_used_s += duration_s
    if status == DutyStatus.D:
        state.shift_driving_s += duration_s
        state.driving_since_break_s += duration_s
        state.non_driving_streak_s = 0
        state.continuous_rest_s = 0
    else:
        # Non-driving
        state.non_driving_streak_s += duration_s
        if status in (DutyStatus.OFF, DutyStatus.SB):
            state.continuous_rest_s += duration_s
        else:
            state.continuous_rest_s = 0
        if state.non_driving_streak_s >= BREAK_REQUIRED_S:
            state.driving_since_break_s = 0

    state.apply_elapsed(duration_s)
    state.now = end
    end_clocks = _snapshot(state.as_driver())

    ev = TimelineEvent(
        event_id=_new_id(),
        event_type=event_type,
        status=status,
        start_utc=start,
        end_utc=end,
        duration_s=duration_s,
        reason_codes=reasons,
        clocks_at_start=start_clocks,
        clocks_at_end=end_clocks,
        start_progress_m=state.route_progress_m,
        end_progress_m=state.route_progress_m,
        distance_m=0,
        start_coord=coord,
        end_coord=coord,
        location_label=label,
        location_provenance=provenance,
        leg_id=leg_id,
    )
    state.events.append(ev)


def _emit_fuel(
    state: SchedulerState,
    settings: PlanningSettings,
    progress: ProgressIndex,
    rest_status: DutyStatus,
) -> None:
    coord = _coord_at(progress, state.route_progress_m)
    label = "Planned rest area along route — facility not verified"
    duration = settings.fuel_duration_s
    reasons: list[ReasonCode] = [ReasonCode.FUEL_INTERVAL]
    _emit_service(
        state,
        event_type=EventType.FUEL,
        status=DutyStatus.ON,
        duration_s=duration,
        reasons=tuple(reasons),
        label=label,
        coord=coord,
        provenance=LocationProvenance.PLANNED_UNVERIFIED,
        leg_id=None,
    )
    state.miles_since_fuel_m = 0
    # If fuel alone did not satisfy 30-min interruption, add adjacent OFF
    if duration < BREAK_REQUIRED_S and state.driving_since_break_s > 0:
        need = BREAK_REQUIRED_S - state.non_driving_streak_s
        if need > 0:
            _emit_service(
                state,
                event_type=EventType.BREAK,
                status=rest_status,
                duration_s=need,
                reasons=(ReasonCode.BREAK_AFTER_DRIVING,),
                label=label,
                coord=coord,
                provenance=LocationProvenance.PLANNED_UNVERIFIED,
                leg_id=None,
            )


def _insert_required_rest(
    state: SchedulerState,
    settings: PlanningSettings,
    rest_status: DutyStatus,
    progress: ProgressIndex,
) -> None:
    """Insert daily rest or cycle restart. Extends continuous OFF/SB; never ON."""
    coord = _coord_at(progress, state.route_progress_m)
    label = "Planned rest area along route — facility not verified"

    need_restart = state.remaining_cycle_driving_s() <= 0
    # Also restart if we cannot finish meaningful work without it and cycle is exhausted
    if need_restart:
        # Extend continuous rest to 34h total
        already = state.continuous_rest_s
        # If currently in a non-rest status streak, continuous_rest may be 0
        needed = max(0, CYCLE_RESTART_S - already)
        if needed == 0:
            needed = CYCLE_RESTART_S
        # If we already have some continuous rest from prior OFF, only add the remainder
        if already > 0 and already < CYCLE_RESTART_S:
            needed = CYCLE_RESTART_S - already
        _emit_rest(
            state,
            duration_s=needed,
            status=rest_status,
            event_type=EventType.RESTART,
            reasons=(ReasonCode.CYCLE_RESTART,),
            label=label,
            coord=coord,
        )
        # Qualifying 34h restart resets cycle
        state.cycle_used_s = 0
        state.shift_driving_s = 0
        state.shift_elapsed_s = 0
        state.driving_since_break_s = 0
        state.shift_window_open = False
        state.shift_window_start = None
        state.continuous_rest_s = CYCLE_RESTART_S
        return

    # Daily 10-hour rest (does not reset cycle)
    already = state.continuous_rest_s
    needed = max(DAILY_REST_S - already, DAILY_REST_S) if already < DAILY_REST_S else DAILY_REST_S
    if already >= DAILY_REST_S:
        # Already rested somehow — still need a fresh 10h block from now for shift reset
        needed = DAILY_REST_S
        already_for_extend = 0
    else:
        needed = DAILY_REST_S - already
        already_for_extend = already

    reasons: list[ReasonCode] = [ReasonCode.DAILY_REST]
    if state.remaining_shift_driving_s() <= 0:
        reasons.append(ReasonCode.SHIFT_DRIVING_LIMIT)
    if state.remaining_window_s() <= 0:
        reasons.append(ReasonCode.SHIFT_WINDOW_LIMIT)
    if state.remaining_before_break_s() <= 0 and state.non_driving_streak_s < BREAK_REQUIRED_S:
        reasons.append(ReasonCode.BREAK_AFTER_DRIVING)

    # Prefer combining: 10h rest also satisfies break
    _emit_rest(
        state,
        duration_s=needed if already_for_extend > 0 else DAILY_REST_S,
        status=rest_status,
        event_type=EventType.REST,
        reasons=tuple(dict.fromkeys(reasons)),
        label=label,
        coord=coord,
    )
    state.shift_driving_s = 0
    state.shift_elapsed_s = 0
    state.driving_since_break_s = 0
    state.shift_window_open = False
    state.shift_window_start = None
    state.continuous_rest_s = max(state.continuous_rest_s, DAILY_REST_S)
    # Cycle NOT reset


def _emit_rest(
    state: SchedulerState,
    *,
    duration_s: int,
    status: DutyStatus,
    event_type: EventType,
    reasons: tuple[ReasonCode, ...],
    label: str,
    coord: Coordinates | None,
) -> None:
    if duration_s <= 0:
        raise ValueError("rest duration must be positive")
    start_clocks = _snapshot(state.as_driver())
    start = state.now
    end = start + timedelta(seconds=duration_s)

    # Rest does not open/advance the 14h window in a meaningful "on duty" way;
    # if window was open, elapsed continues only for on-duty — FMCSA: 14h is
    # consecutive hours from first on-duty, including off-duty short breaks.
    # Ordinary short breaks do NOT pause it; a qualifying 10h rest ends the day.
    # During a qualifying rest we close the window rather than accumulate.
    state.non_driving_streak_s += duration_s
    state.continuous_rest_s += duration_s
    if state.non_driving_streak_s >= BREAK_REQUIRED_S:
        state.driving_since_break_s = 0
    # Qualifying rest ends the shift window
    if duration_s + (start_clocks.continuous_rest_s) >= DAILY_REST_S or duration_s >= DAILY_REST_S:
        state.shift_window_open = False
        state.shift_elapsed_s = 0
        state.shift_driving_s = 0
    elif state.shift_window_open:
        # Short rest inside window still consumes window
        state.apply_elapsed(duration_s)

    state.now = end
    end_clocks = _snapshot(state.as_driver())
    ev = TimelineEvent(
        event_id=_new_id(),
        event_type=event_type,
        status=status,
        start_utc=start,
        end_utc=end,
        duration_s=duration_s,
        reason_codes=reasons,
        clocks_at_start=start_clocks,
        clocks_at_end=end_clocks,
        start_progress_m=state.route_progress_m,
        end_progress_m=state.route_progress_m,
        distance_m=0,
        start_coord=coord,
        end_coord=coord,
        location_label=label,
        location_provenance=LocationProvenance.PLANNED_UNVERIFIED,
        leg_id=None,
    )
    state.events.append(ev)
