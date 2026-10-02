"""Serialization helpers between domain objects and JSON."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from trips.domain.types import (
    ClockSnapshot,
    Coordinates,
    DailyLogSheet,
    DutyStatus,
    EventType,
    LocationProvenance,
    ReasonCode,
    Remark,
    RouteLeg,
    RouteStep,
    StatusSegment,
    TimelineEvent,
)


def coords_to_dict(c: Coordinates | None) -> dict[str, float] | None:
    if c is None:
        return None
    return {"lat": c.lat, "lon": c.lon}


def event_to_dict(ev: TimelineEvent) -> dict[str, Any]:
    return {
        "event_id": ev.event_id,
        "event_type": ev.event_type.value,
        "status": ev.status.value,
        "start_utc": ev.start_utc.isoformat(),
        "end_utc": ev.end_utc.isoformat(),
        "duration_s": ev.duration_s,
        "reason_codes": [r.value for r in ev.reason_codes],
        "clocks_at_start": _clocks(ev.clocks_at_start),
        "clocks_at_end": _clocks(ev.clocks_at_end),
        "start_progress_m": ev.start_progress_m,
        "end_progress_m": ev.end_progress_m,
        "distance_m": ev.distance_m,
        "start_coord": coords_to_dict(ev.start_coord),
        "end_coord": coords_to_dict(ev.end_coord),
        "location_label": ev.location_label,
        "location_provenance": ev.location_provenance.value if ev.location_provenance else None,
        "leg_id": ev.leg_id,
        "explanation": ev.explanation,
    }


def _clocks(c: ClockSnapshot) -> dict[str, int]:
    return {
        "shift_driving_s": c.shift_driving_s,
        "shift_elapsed_s": c.shift_elapsed_s,
        "driving_since_break_s": c.driving_since_break_s,
        "cycle_used_s": c.cycle_used_s,
        "miles_since_fuel_m": c.miles_since_fuel_m,
        "continuous_rest_s": c.continuous_rest_s,
    }


def leg_to_dict(leg: RouteLeg) -> dict[str, Any]:
    return {
        "leg_id": leg.leg_id,
        "from_label": leg.from_label,
        "to_label": leg.to_label,
        "distance_m": leg.distance_m,
        "duration_s": leg.duration_s,
        "geometry": [[lon, lat] for lon, lat in leg.geometry_lon_lat],
        "steps": [
            {
                "distance_m": s.distance_m,
                "duration_s": s.duration_s,
                "instruction": s.instruction,
                "geometry": [[lon, lat] for lon, lat in s.geometry_lon_lat],
            }
            for s in leg.steps
        ],
        "provider": leg.provider,
        "profile": leg.profile,
        "fetched_at": leg.fetched_at.isoformat(),
        "route_version": leg.route_version,
    }


def log_to_dict(sheet: DailyLogSheet) -> dict[str, Any]:
    return {
        "date_local": sheet.date_local.isoformat(),
        "from_label": sheet.from_label,
        "to_label": sheet.to_label,
        "timezone": sheet.timezone,
        "utc_offset": sheet.utc_offset,
        "driving_miles": sheet.driving_miles,
        "total_miles": sheet.total_miles,
        "segments": [
            {
                "status": s.status.value,
                "start_s": s.start_s,
                "end_s": s.end_s,
                "event_id": s.event_id,
                "is_planning_filler": s.is_planning_filler,
            }
            for s in sheet.segments
        ],
        "totals_s": sheet.totals_s,
        "remarks": [
            {
                "time_local": r.time_local.isoformat(),
                "text": r.text,
                "location_label": r.location_label,
                "event_id": r.event_id,
                "estimated": r.estimated,
            }
            for r in sheet.remarks
        ],
        "recap": sheet.recap,
        "page_number": sheet.page_number,
        "total_pages": sheet.total_pages,
        "carrier_name": sheet.carrier_name,
        "main_office": sheet.main_office,
        "home_terminal": sheet.home_terminal,
        "tractor_trailer": sheet.tractor_trailer,
        "driver_name": sheet.driver_name,
        "co_driver": sheet.co_driver,
        "shipping_document": sheet.shipping_document,
        "shipper_commodity": sheet.shipper_commodity,
        "planned_banner": sheet.planned_banner,
        "signature": None,
    }
