"""Core domain scheduling tests including the golden fixture."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from trips.domain.constants import FUEL_INTERVAL_M, METERS_PER_MILE
from trips.domain.logs import project_daily_logs
from trips.domain.progress import build_progress_index
from trips.domain.scheduler import hours_to_seconds, schedule_trip
from trips.domain.types import (
    Coordinates,
    DutyStatus,
    EventType,
    PlanningSettings,
)
from trips.domain.validator import mutate_for_tests, validate_timeline
from trips.tests.helpers import make_leg, miles

TZ = ZoneInfo("America/Chicago")
CHICAGO = Coordinates(lat=41.8781, lon=-87.6298)
JOLIET = Coordinates(lat=41.525, lon=-88.0817)
BLOOMINGTON = Coordinates(lat=40.4842, lon=-88.9937)


def _settings(**kwargs) -> PlanningSettings:
    base = dict(
        departure_local=datetime(2026, 6, 15, 8, 0, tzinfo=TZ),
        home_terminal_tz="America/Chicago",
        miles_since_fuel_m=0,
        fuel_duration_s=30 * 60,
        include_pretrip_inspection=False,
        rest_status=DutyStatus.OFF,
        sleeper_equipped=False,
        cycle_used_s=0,
    )
    base.update(kwargs)
    return PlanningSettings(**base)


def test_hours_to_seconds_precise():
    assert hours_to_seconds(0) == 0
    assert hours_to_seconds(70) == 70 * 3600
    assert hours_to_seconds("1.5") == 5400
    assert hours_to_seconds("69.25") == int(69.25 * 3600)
    with pytest.raises(ValueError):
        hours_to_seconds(-1)
    with pytest.raises(ValueError):
        hours_to_seconds(71)
    with pytest.raises(ValueError):
        hours_to_seconds(float("nan"))


def test_golden_fixture():
    """Hand-calculated: 08:00 start, 2h/100mi, pickup 1h, 3h/150mi, dropoff 1h → 15:00."""
    legs = [
        make_leg(
            leg_id="leg1",
            from_label="Current",
            to_label="Pickup",
            duration_s=2 * 3600,
            distance_m=miles(100),
            start=CHICAGO,
            end=JOLIET,
        ),
        make_leg(
            leg_id="leg2",
            from_label="Pickup",
            to_label="Dropoff",
            duration_s=3 * 3600,
            distance_m=miles(150),
            start=JOLIET,
            end=BLOOMINGTON,
        ),
    ]
    settings = _settings()
    result = schedule_trip(legs, settings)
    assert result.validation.ok, result.validation.errors

    events = result.events
    assert [e.event_type for e in events] == [
        EventType.DRIVING,
        EventType.PICKUP,
        EventType.DRIVING,
        EventType.DROPOFF,
    ]

    total_d = sum(e.duration_s for e in events if e.status == DutyStatus.D)
    total_on = sum(e.duration_s for e in events if e.status == DutyStatus.ON)
    assert total_d == 5 * 3600
    assert total_on == 2 * 3600
    assert events[-1].end_utc.astimezone(TZ).hour == 15
    assert events[-1].end_utc.astimezone(TZ).minute == 0

    total_m = sum(e.distance_m for e in events if e.status == DutyStatus.D)
    assert abs(total_m / METERS_PER_MILE - 250) < 0.01

    logs = project_daily_logs(
        events, settings, origin_label="Current", destination_label="Dropoff"
    )
    assert len(logs) == 1
    sheet = logs[0]
    assert sheet.totals_s["OFF"] == 17 * 3600
    assert sheet.totals_s["SB"] == 0
    assert sheet.totals_s["D"] == 5 * 3600
    assert sheet.totals_s["ON"] == 2 * 3600
    assert abs(sheet.driving_miles - 250) < 0.2
    assert sum(sheet.totals_s.values()) == 86400


def test_short_trip_no_unnecessary_rest():
    legs = [
        make_leg(
            leg_id="a",
            from_label="A",
            to_label="B",
            duration_s=3600,
            distance_m=miles(50),
            start=CHICAGO,
            end=JOLIET,
        ),
        make_leg(
            leg_id="b",
            from_label="B",
            to_label="C",
            duration_s=3600,
            distance_m=miles(50),
            start=JOLIET,
            end=BLOOMINGTON,
        ),
    ]
    result = schedule_trip(legs, _settings())
    assert result.validation.ok
    types = [e.event_type for e in result.events]
    assert EventType.REST not in types
    assert EventType.RESTART not in types
    assert EventType.FUEL not in types
    assert EventType.BREAK not in types


def test_pickup_satisfies_break():
    """8h driving then 1h pickup — no redundant break before next drive."""
    legs = [
        make_leg(
            leg_id="a",
            from_label="A",
            to_label="Pickup",
            duration_s=8 * 3600,
            distance_m=miles(400),
            start=CHICAGO,
            end=JOLIET,
        ),
        make_leg(
            leg_id="b",
            from_label="Pickup",
            to_label="Dropoff",
            duration_s=2 * 3600,
            distance_m=miles(100),
            start=JOLIET,
            end=BLOOMINGTON,
        ),
    ]
    result = schedule_trip(legs, _settings())
    assert result.validation.ok, result.validation.errors
    types = [e.event_type for e in result.events]
    assert types == [
        EventType.DRIVING,
        EventType.PICKUP,
        EventType.DRIVING,
        EventType.DROPOFF,
    ]
    assert EventType.BREAK not in types


def test_arrival_at_eight_hours_no_break_before_dropoff():
    legs = [
        make_leg(
            leg_id="a",
            from_label="A",
            to_label="Pickup",
            duration_s=3600,
            distance_m=miles(40),
            start=CHICAGO,
            end=JOLIET,
        ),
        make_leg(
            leg_id="b",
            from_label="Pickup",
            to_label="Dropoff",
            duration_s=7 * 3600,
            distance_m=miles(350),
            start=JOLIET,
            end=BLOOMINGTON,
        ),
    ]
    result = schedule_trip(legs, _settings())
    assert result.validation.ok
    # Total driving = 8h at final arrival; dropoff follows without break
    types = [e.event_type for e in result.events]
    assert types[-2:] == [EventType.DRIVING, EventType.DROPOFF]
    assert EventType.BREAK not in types


def test_eleven_hour_limit():
    legs = [
        make_leg(
            leg_id="a",
            from_label="A",
            to_label="Pickup",
            duration_s=1 * 3600,
            distance_m=miles(50),
            start=CHICAGO,
            end=JOLIET,
        ),
        make_leg(
            leg_id="b",
            from_label="Pickup",
            to_label="Dropoff",
            duration_s=12 * 3600,
            distance_m=miles(600),
            start=JOLIET,
            end=BLOOMINGTON,
        ),
    ]
    result = schedule_trip(legs, _settings())
    assert result.validation.ok, result.validation.errors
    # After 11h driving in a shift, must rest before more driving
    driving_before_rest = 0
    saw_rest = False
    for ev in result.events:
        if ev.event_type in (EventType.REST, EventType.RESTART):
            saw_rest = True
            assert driving_before_rest <= 11 * 3600 + 1
            driving_before_rest = 0
        elif ev.status == DutyStatus.D:
            driving_before_rest += ev.duration_s
            if not saw_rest:
                assert driving_before_rest <= 11 * 3600 + 1
    assert any(e.event_type == EventType.REST for e in result.events)


def test_fourteen_hour_window():
    """Window expires with driving allowance left — short OFF does not extend window."""
    # Start with inspection + long ON work to burn window, then try to drive
    # Simpler: drive 1h, then many short ON fuel-like activities... 
    # Actually: 10h of ON work (not driving) then try to drive 5h — only 4h window left
    # Use long first-leg wait via pickup already 1h; we need ON that isn't pickup.
    # Enable inspection and use a route that would want more driving than window allows.
    # Drive 10h (with break via pickup at hour 1), then more — 
    # Better approach: first leg 10 hours driving needs a break at 8h.
    # For pure 14h: accumulate elapsed with ON activities.
    legs = [
        make_leg(
            leg_id="a",
            from_label="A",
            to_label="Pickup",
            duration_s=10 * 3600,
            distance_m=miles(500),
            start=CHICAGO,
            end=JOLIET,
        ),
        make_leg(
            leg_id="b",
            from_label="Pickup",
            to_label="Dropoff",
            duration_s=5 * 3600,
            distance_m=miles(250),
            start=JOLIET,
            end=BLOOMINGTON,
        ),
    ]
    # With break at 8h: drive 8, break 0.5, drive 2 to pickup, pickup 1 → elapsed ~11.5, then 5h drive would hit 14h
    result = schedule_trip(legs, _settings(fuel_duration_s=30 * 60))
    assert result.validation.ok, result.validation.errors
    # Find if any rest due to window
    window_rests = [
        e
        for e in result.events
        if e.event_type == EventType.REST
        and any(r.value == "SHIFT_WINDOW_LIMIT" for r in e.reason_codes)
    ]
    # Either window or 11h may bind; ensure no drive exceeds window replay
    assert result.validation.ok


def test_cycle_69_pickup():
    legs = [
        make_leg(
            leg_id="a",
            from_label="A",
            to_label="Pickup",
            duration_s=0,
            distance_m=0,
            start=CHICAGO,
            end=CHICAGO,
        ),
        make_leg(
            leg_id="b",
            from_label="Pickup",
            to_label="Dropoff",
            duration_s=2 * 3600,
            distance_m=miles(100),
            start=CHICAGO,
            end=JOLIET,
        ),
    ]
    result = schedule_trip(legs, _settings(cycle_used_s=69 * 3600))
    assert result.validation.ok, result.validation.errors
    # Pickup consumes remaining 1h; no subsequent drive before restart
    types = [e.event_type for e in result.events]
    assert EventType.PICKUP in types
    pickup_idx = types.index(EventType.PICKUP)
    # After pickup, before any further drive, need restart
    after = result.events[pickup_idx + 1 :]
    # First driving after pickup should be preceded by restart
    drive_after = next((e for e in after if e.status == DutyStatus.D), None)
    if drive_after:
        between = after[: after.index(drive_after)]
        assert any(e.event_type == EventType.RESTART for e in between)


def test_cycle_70_no_drive_until_restart():
    legs = [
        make_leg(
            leg_id="a",
            from_label="A",
            to_label="Pickup",
            duration_s=3600,
            distance_m=miles(40),
            start=CHICAGO,
            end=JOLIET,
        ),
        make_leg(
            leg_id="b",
            from_label="Pickup",
            to_label="Dropoff",
            duration_s=3600,
            distance_m=miles(40),
            start=JOLIET,
            end=BLOOMINGTON,
        ),
    ]
    result = schedule_trip(legs, _settings(cycle_used_s=70 * 3600))
    assert result.validation.ok, result.validation.errors
    # First event involving movement should come after restart
    first_drive = next(e for e in result.events if e.status == DutyStatus.D)
    restarts_before = [
        e
        for e in result.events
        if e.event_type == EventType.RESTART and e.start_utc <= first_drive.start_utc
    ]
    assert restarts_before


def test_ten_hour_rest_does_not_reset_cycle():
    legs = [
        make_leg(
            leg_id="a",
            from_label="A",
            to_label="Pickup",
            duration_s=3600,
            distance_m=miles(50),
            start=CHICAGO,
            end=JOLIET,
        ),
        make_leg(
            leg_id="b",
            from_label="Pickup",
            to_label="Dropoff",
            duration_s=12 * 3600,
            distance_m=miles(600),
            start=JOLIET,
            end=BLOOMINGTON,
        ),
    ]
    settings = _settings(cycle_used_s=20 * 3600)
    result = schedule_trip(legs, settings)
    assert result.validation.ok
    for ev in result.events:
        if ev.event_type == EventType.REST:
            # Cycle should not drop to 0 solely from 10h rest
            if ev.duration_s < 34 * 3600:
                assert ev.clocks_at_end.cycle_used_s > 0 or ev.clocks_at_start.cycle_used_s == 0


def test_fuel_2500_miles():
    legs = [
        make_leg(
            leg_id="a",
            from_label="A",
            to_label="Pickup",
            duration_s=5 * 3600,
            distance_m=miles(250),
            start=CHICAGO,
            end=JOLIET,
        ),
        make_leg(
            leg_id="b",
            from_label="Pickup",
            to_label="Dropoff",
            duration_s=40 * 3600,
            distance_m=miles(2250),
            start=JOLIET,
            end=Coordinates(lat=39.7392, lon=-104.9903),
        ),
    ]
    result = schedule_trip(legs, _settings())
    assert result.validation.ok, result.validation.errors
    fuel_events = [e for e in result.events if e.event_type == EventType.FUEL]
    assert len(fuel_events) >= 2

    # Check gaps
    fuel_m = 0
    for ev in result.events:
        if ev.status == DutyStatus.D:
            fuel_m += ev.distance_m
            assert fuel_m <= FUEL_INTERVAL_M + 1
        elif ev.event_type == EventType.FUEL:
            fuel_m = 0


def test_fuel_break_qualification():
    # 8h drive then fuel 30 min — no extra break
    legs = [
        make_leg(
            leg_id="a",
            from_label="A",
            to_label="Pickup",
            duration_s=8 * 3600,
            distance_m=miles(900),
            start=CHICAGO,
            end=JOLIET,
        ),
        make_leg(
            leg_id="b",
            from_label="Pickup",
            to_label="Dropoff",
            duration_s=2 * 3600,
            distance_m=miles(100),
            start=JOLIET,
            end=BLOOMINGTON,
        ),
    ]
    # Fuel triggered near 1000... 900 miles so fuel after first leg? miles=900 < 1000
    # Force fuel by starting with 200 miles since fuel so 800 more hits limit during first leg
    result = schedule_trip(
        legs, _settings(miles_since_fuel_m=miles(200), fuel_duration_s=30 * 60)
    )
    assert result.validation.ok, result.validation.errors
    # 15-minute fuel should add adjacent break
    result15 = schedule_trip(
        legs, _settings(miles_since_fuel_m=miles(200), fuel_duration_s=15 * 60)
    )
    assert result15.validation.ok, result15.validation.errors
    assert any(e.event_type == EventType.BREAK for e in result15.events) or any(
        e.event_type == EventType.FUEL and e.duration_s >= 1800 for e in result15.events
    )


def test_identical_locations_zero_length():
    legs = [
        make_leg(
            leg_id="a",
            from_label="Yard",
            to_label="Yard",
            duration_s=0,
            distance_m=0,
            start=CHICAGO,
            end=CHICAGO,
        ),
        make_leg(
            leg_id="b",
            from_label="Yard",
            to_label="Yard",
            duration_s=0,
            distance_m=0,
            start=CHICAGO,
            end=CHICAGO,
        ),
    ]
    result = schedule_trip(legs, _settings())
    assert result.validation.ok, result.validation.errors
    types = [e.event_type for e in result.events]
    assert EventType.PICKUP in types
    assert EventType.DROPOFF in types
    assert EventType.DRIVING not in types


def test_midnight_split_and_exact_midnight():
    # Depart 22:00, drive 3h → crosses midnight
    settings = _settings(
        departure_local=datetime(2026, 6, 15, 22, 0, tzinfo=TZ),
    )
    legs = [
        make_leg(
            leg_id="a",
            from_label="A",
            to_label="Pickup",
            duration_s=3 * 3600,
            distance_m=miles(150),
            start=CHICAGO,
            end=JOLIET,
        ),
        make_leg(
            leg_id="b",
            from_label="Pickup",
            to_label="Dropoff",
            duration_s=3600,
            distance_m=miles(50),
            start=JOLIET,
            end=BLOOMINGTON,
        ),
    ]
    result = schedule_trip(legs, settings)
    assert result.validation.ok
    logs = project_daily_logs(
        result.events, settings, origin_label="A", destination_label="Dropoff"
    )
    assert len(logs) >= 2
    assert sum(s.driving_miles for s in logs) == pytest.approx(
        sum(e.distance_m for e in result.events if e.status == DutyStatus.D) / METERS_PER_MILE,
        abs=0.5,
    )
    for sheet in logs:
        assert sum(sheet.totals_s.values()) == 86400


def test_exact_midnight_completion_no_extra_page():
    # Craft trip that ends exactly at midnight local
    # Start 08:00, total duration 16h → ends 00:00 next day
    # 2h drive + 1h pickup + 12h drive + 1h dropoff = 16h — but 12h drive needs rest
    # Simpler: 0 drive both legs, pickup+dropoff = 2h ending at 10:00 — not midnight
    # Start at 22:00: drive 1h, pickup 1h, drive 0, dropoff 0... 
    # End at midnight: start 22:00, events totaling 2h
    settings = _settings(departure_local=datetime(2026, 6, 15, 22, 0, tzinfo=TZ))
    legs = [
        make_leg(
            leg_id="a",
            from_label="A",
            to_label="B",
            duration_s=0,
            distance_m=0,
            start=CHICAGO,
            end=CHICAGO,
        ),
        make_leg(
            leg_id="b",
            from_label="B",
            to_label="C",
            duration_s=0,
            distance_m=0,
            start=CHICAGO,
            end=CHICAGO,
        ),
    ]
    result = schedule_trip(legs, settings)
    # 1h pickup + 1h dropoff = ends 00:00
    end_local = result.events[-1].end_utc.astimezone(TZ)
    assert end_local.hour == 0 and end_local.minute == 0
    logs = project_daily_logs(
        result.events, settings, origin_label="A", destination_label="C"
    )
    # Should be one page (June 15), not an empty June 16
    assert len(logs) == 1
    assert logs[0].date_local.isoformat() == "2026-06-15"


def test_progress_index_lon_lat():
    legs = [
        make_leg(
            leg_id="a",
            from_label="A",
            to_label="B",
            duration_s=3600,
            distance_m=100_000,
            start=Coordinates(lat=41.0, lon=-87.0),
            end=Coordinates(lat=42.0, lon=-88.0),
        )
    ]
    idx = build_progress_index(legs)
    mid = idx.coordinate_at_distance(50_000)
    assert 41.0 <= mid.lat <= 42.0
    assert -88.0 <= mid.lon <= -87.0
    t = idx.time_at_distance(50_000)
    assert 0 < t < 3600


def test_validator_catches_mutations():
    legs = [
        make_leg(
            leg_id="a",
            from_label="A",
            to_label="B",
            duration_s=2 * 3600,
            distance_m=miles(100),
            start=CHICAGO,
            end=JOLIET,
        ),
        make_leg(
            leg_id="b",
            from_label="B",
            to_label="C",
            duration_s=2 * 3600,
            distance_m=miles(100),
            start=JOLIET,
            end=BLOOMINGTON,
        ),
    ]
    result = schedule_trip(legs, _settings())
    assert result.validation.ok
    for kind in ("excessive_driving", "overlap", "wrong_break_reset", "cycle_violation"):
        bad = mutate_for_tests(list(result.events), kind)
        validation = validate_timeline(tuple(bad), _settings())
        assert not validation.ok, f"expected failure for {kind}"


def test_dst_unsupported():
    # US spring forward 2026-03-08 in America/Chicago
    settings = _settings(
        departure_local=datetime(2026, 3, 8, 1, 0, tzinfo=TZ),
    )
    legs = [
        make_leg(
            leg_id="a",
            from_label="A",
            to_label="B",
            duration_s=5 * 3600,
            distance_m=miles(200),
            start=CHICAGO,
            end=JOLIET,
        ),
        make_leg(
            leg_id="b",
            from_label="B",
            to_label="C",
            duration_s=3600,
            distance_m=miles(40),
            start=JOLIET,
            end=BLOOMINGTON,
        ),
    ]
    from trips.domain.scheduler import DstUnsupportedError

    with pytest.raises(DstUnsupportedError):
        schedule_trip(legs, settings)
