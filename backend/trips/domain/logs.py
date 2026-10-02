"""Project a canonical timeline onto home-terminal daily log sheets."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from .constants import METERS_PER_MILE, SECONDS_PER_DAY
from .types import (
    DailyLogSheet,
    DutyStatus,
    EventType,
    PlanningSettings,
    Remark,
    StatusSegment,
    TimelineEvent,
)


def project_daily_logs(
    events: tuple[TimelineEvent, ...] | list[TimelineEvent],
    settings: PlanningSettings,
    *,
    origin_label: str,
    destination_label: str,
) -> tuple[DailyLogSheet, ...]:
    """Split events at terminal midnights; pad to 24h with assumed OFF."""
    if not events:
        return ()

    tz = ZoneInfo(settings.home_terminal_tz)
    trip_start = events[0].start_utc
    trip_end = events[-1].end_utc

    # Exact midnight completion: end_local time is 00:00:00 → last day is previous
    end_local = trip_end.astimezone(tz)
    start_local = trip_start.astimezone(tz)

    first_day = start_local.date()
    if end_local.hour == 0 and end_local.minute == 0 and end_local.second == 0 and end_local.microsecond == 0:
        last_day = (end_local - timedelta(seconds=1)).date()
    else:
        last_day = end_local.date()

    days: list[date] = []
    d = first_day
    while d <= last_day:
        days.append(d)
        d += timedelta(days=1)

    sheets: list[DailyLogSheet] = []
    for page_i, day in enumerate(days):
        day_start_local = datetime(day.year, day.month, day.day, tzinfo=tz)
        day_end_local = day_start_local + timedelta(days=1)
        day_start_utc = day_start_local.astimezone(timezone.utc)
        day_end_utc = day_end_local.astimezone(timezone.utc)

        if int((day_end_utc - day_start_utc).total_seconds()) != SECONDS_PER_DAY:
            raise ValueError(
                f"DST transition day {day.isoformat()} unsupported in {settings.home_terminal_tz}"
            )

        segments: list[StatusSegment] = []
        remarks: list[Remark] = []
        driving_m = 0
        day_duty_s = 0  # D + ON for recap (excluding planning fillers)

        # Assumed OFF before first trip activity on first day
        if day == first_day and trip_start > day_start_utc:
            pre = int((trip_start - day_start_utc).total_seconds())
            segments.append(
                StatusSegment(
                    status=DutyStatus.OFF,
                    start_s=0,
                    end_s=pre,
                    event_id="assumed-off-pre",
                    is_planning_filler=True,
                )
            )

        for ev in events:
            # Intersect event with this day [day_start, day_end)
            if ev.end_utc <= day_start_utc or ev.start_utc >= day_end_utc:
                continue
            seg_start = max(ev.start_utc, day_start_utc)
            seg_end = min(ev.end_utc, day_end_utc)
            start_s = int((seg_start - day_start_utc).total_seconds())
            end_s = int((seg_end - day_start_utc).total_seconds())
            if end_s <= start_s:
                continue

            # Proportional distance for midnight-split driving
            if ev.distance_m > 0 and ev.duration_s > 0:
                frac = (end_s - start_s) / ev.duration_s
                driving_m += int(round(ev.distance_m * frac))
            elif ev.distance_m > 0 and seg_start == ev.start_utc and seg_end == ev.end_utc:
                driving_m += ev.distance_m

            segments.append(
                StatusSegment(
                    status=ev.status,
                    start_s=start_s,
                    end_s=end_s,
                    event_id=ev.event_id,
                    is_planning_filler=False,
                )
            )
            if ev.status in (DutyStatus.D, DutyStatus.ON):
                day_duty_s += end_s - start_s

            # Remark at transition (start of event) if it falls on this day
            if day_start_utc <= ev.start_utc < day_end_utc:
                remarks.append(
                    Remark(
                        time_local=ev.start_utc.astimezone(tz),
                        text=_remark_text(ev),
                        location_label=ev.location_label,
                        event_id=ev.event_id,
                        estimated=ev.location_provenance.value == "ROUTE_INTERPOLATED"
                        if ev.location_provenance
                        else False,
                    )
                )

        # Assumed OFF after trip completion on last activity day
        if trip_end < day_end_utc and trip_end > day_start_utc:
            post_start = int((trip_end - day_start_utc).total_seconds())
            if post_start < SECONDS_PER_DAY:
                segments.append(
                    StatusSegment(
                        status=DutyStatus.OFF,
                        start_s=post_start,
                        end_s=SECONDS_PER_DAY,
                        event_id="assumed-off-post",
                        is_planning_filler=True,
                    )
                )
        elif day > last_day:
            pass
        elif trip_end <= day_start_utc:
            # Full day after trip — should not happen given last_day logic
            segments.append(
                StatusSegment(
                    status=DutyStatus.OFF,
                    start_s=0,
                    end_s=SECONDS_PER_DAY,
                    event_id="assumed-off-full",
                    is_planning_filler=True,
                )
            )

        # Full rest days entirely within trip (e.g. restart) already covered by events

        # If day is entirely within a long rest and no segments yet
        if not segments:
            segments.append(
                StatusSegment(
                    status=DutyStatus.OFF,
                    start_s=0,
                    end_s=SECONDS_PER_DAY,
                    event_id="assumed-off-empty",
                    is_planning_filler=False,
                )
            )

        segments = _merge_adjacent(segments)
        totals = _totals(segments)
        total_seg = sum(totals.values())
        if total_seg != SECONDS_PER_DAY:
            # Repair tiny rounding by adjusting last filler
            diff = SECONDS_PER_DAY - total_seg
            if segments and abs(diff) <= 2:
                last = segments[-1]
                segments[-1] = StatusSegment(
                    status=last.status,
                    start_s=last.start_s,
                    end_s=last.end_s + diff,
                    event_id=last.event_id,
                    is_planning_filler=last.is_planning_filler,
                )
                totals = _totals(segments)

        driving_miles = driving_m / METERS_PER_MILE
        recap = _recap(day_duty_s, settings)

        from_label = origin_label if day == first_day else _day_from_to(events, day_start_utc, day_end_utc, "from")
        to_label = destination_label if day == last_day else _day_from_to(events, day_start_utc, day_end_utc, "to")

        offset = day_start_local.strftime("%z")
        utc_offset = f"{offset[:3]}:{offset[3:]}" if offset else "+00:00"

        sheets.append(
            DailyLogSheet(
                date_local=day,
                from_label=from_label or origin_label,
                to_label=to_label or destination_label,
                timezone=settings.home_terminal_tz,
                utc_offset=utc_offset,
                driving_miles=round(driving_miles, 1),
                total_miles=round(driving_miles, 1),  # single-driver assumption
                segments=tuple(segments),
                totals_s=totals,
                remarks=tuple(remarks),
                recap=recap,
                page_number=page_i + 1,
                total_pages=len(days),
                carrier_name=settings.carrier_name,
                main_office=settings.main_office,
                home_terminal=settings.home_terminal,
                tractor_trailer=settings.tractor_trailer,
                driver_name=settings.driver_name,
                co_driver=settings.co_driver,
                shipping_document=settings.shipping_document,
                shipper_commodity=settings.shipper_commodity,
            )
        )

    # Fix total_pages on all sheets
    total = len(sheets)
    return tuple(
        DailyLogSheet(
            date_local=s.date_local,
            from_label=s.from_label,
            to_label=s.to_label,
            timezone=s.timezone,
            utc_offset=s.utc_offset,
            driving_miles=s.driving_miles,
            total_miles=s.total_miles,
            segments=s.segments,
            totals_s=s.totals_s,
            remarks=s.remarks,
            recap=s.recap,
            page_number=s.page_number,
            total_pages=total,
            carrier_name=s.carrier_name,
            main_office=s.main_office,
            home_terminal=s.home_terminal,
            tractor_trailer=s.tractor_trailer,
            driver_name=s.driver_name,
            co_driver=s.co_driver,
            shipping_document=s.shipping_document,
            shipper_commodity=s.shipper_commodity,
        )
        for s in sheets
    )


def _remark_text(ev: TimelineEvent) -> str:
    base = {
        EventType.PICKUP: "Pickup (on duty not driving)",
        EventType.DROPOFF: "Dropoff (on duty not driving)",
        EventType.FUEL: "Fuel stop (planned, facility not verified)",
        EventType.BREAK: "Break / driving interruption",
        EventType.REST: "Off duty rest (10-hour qualifying)",
        EventType.RESTART: "34-hour restart",
        EventType.INSPECTION: "Pre-trip inspection",
        EventType.DRIVING: "Driving",
    }.get(ev.event_type, ev.event_type.value)
    loc = f" @ {ev.location_label}" if ev.location_label else ""
    return f"{base}{loc}"


def _merge_adjacent(segments: list[StatusSegment]) -> list[StatusSegment]:
    if not segments:
        return segments
    segments = sorted(segments, key=lambda s: s.start_s)
    merged: list[StatusSegment] = [segments[0]]
    for seg in segments[1:]:
        last = merged[-1]
        if (
            seg.status == last.status
            and seg.start_s == last.end_s
            and seg.is_planning_filler == last.is_planning_filler
        ):
            merged[-1] = StatusSegment(
                status=last.status,
                start_s=last.start_s,
                end_s=seg.end_s,
                event_id=last.event_id,
                is_planning_filler=last.is_planning_filler,
            )
        else:
            merged.append(seg)
    return merged


def _totals(segments: list[StatusSegment]) -> dict[str, int]:
    totals = {"OFF": 0, "SB": 0, "D": 0, "ON": 0}
    for seg in segments:
        totals[seg.status.value] += seg.end_s - seg.start_s
    return totals


def _recap(day_duty_s: int, settings: PlanningSettings) -> dict[str, Any]:
    """Conservative cycle recap — unknown history labeled."""
    return {
        "on_duty_hours_today_s": day_duty_s,
        "cycle_mode": "conservative_estimate",
        "hours_70_8": {
            "A_total_last_7_including_today": "History required",
            "B_available_tomorrow": "History required",
            "C_total_last_8_including_today": "History required",
            "note": (
                "Conservative cycle estimate carries the entered cycle total forward "
                "until a 34-hour restart; daily history was not supplied."
            ),
        },
        "hours_60_7": {
            "applicable": False,
            "note": "60-hour/7-day option is not applicable for this planner.",
        },
        "initial_cycle_used_s": settings.cycle_used_s,
    }


def _day_from_to(
    events: list[TimelineEvent] | tuple[TimelineEvent, ...],
    day_start: datetime,
    day_end: datetime,
    which: str,
) -> str:
    day_events = [
        e
        for e in events
        if e.end_utc > day_start and e.start_utc < day_end and e.location_label
    ]
    if not day_events:
        return ""
    if which == "from":
        return day_events[0].location_label or ""
    return day_events[-1].location_label or ""
