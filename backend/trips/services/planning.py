"""Trip planning orchestration service."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings

from trips.domain.constants import (
    CONTIGUOUS_US_LAT,
    CONTIGUOUS_US_LON,
    CYCLE_LIMIT_S,
    FUEL_INTERVAL_M,
    RULE_VERSION,
    SCHEMA_VERSION,
)
from trips.domain.logs import project_daily_logs
from trips.domain.scheduler import (
    DstUnsupportedError,
    UnsupportedTripError,
    hours_to_seconds,
    schedule_trip,
)
from trips.domain.types import Coordinates, DutyStatus, PlanningSettings
from trips.models import TripPlan
from trips.providers.base import NoRouteFound, ProviderError, QuotaExceeded
from trips.providers.fake import FakeRoutingProvider
from trips.providers.openrouteservice import OpenRouteServiceProvider
from trips.services.serialize import event_to_dict, leg_to_dict, log_to_dict


class PlanError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "PLAN_ERROR",
        status: int = 400,
        field_errors: dict | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status
        self.field_errors = field_errors or {}
        self.retryable = retryable


def get_provider():
    if settings.USE_FAKE_PROVIDER:
        return FakeRoutingProvider()
    return OpenRouteServiceProvider()


def _parse_location(data: dict, field: str) -> tuple[str, Coordinates]:
    if not isinstance(data, dict):
        raise PlanError(f"{field} is required", field_errors={field: ["Required"]})
    label = (data.get("label") or "").strip()
    coords = data.get("coordinates") or {}
    try:
        lat = float(coords.get("lat"))
        lon = float(coords.get("lon"))
    except (TypeError, ValueError):
        raise PlanError(
            f"{field} must include resolved coordinates",
            field_errors={field: ["Select a location from search results"]},
        )
    if not label:
        raise PlanError(f"{field} label is required", field_errors={field: ["Required"]})
    if not (
        CONTIGUOUS_US_LAT[0] <= lat <= CONTIGUOUS_US_LAT[1]
        and CONTIGUOUS_US_LON[0] <= lon <= CONTIGUOUS_US_LON[1]
    ):
        raise PlanError(
            "Supported routes are limited to the contiguous United States",
            code="UNSUPPORTED_REGION",
            field_errors={field: ["Location must be in the contiguous United States"]},
        )
    return label, Coordinates(lat=lat, lon=lon)


def _parse_cycle_hours(raw: Any) -> int:
    if raw is None or raw == "":
        raise PlanError(
            "Current Cycle Used is required",
            field_errors={"cycle_used_hours": ["Required"]},
        )
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        raise PlanError(
            "Current Cycle Used must be a finite number",
            field_errors={"cycle_used_hours": ["Must be a finite number"]},
        )
    if not value.is_finite():
        raise PlanError(
            "Current Cycle Used must be a finite number",
            field_errors={"cycle_used_hours": ["Must be a finite number"]},
        )
    if value < 0 or value > 70:
        raise PlanError(
            "Current Cycle Used must be between 0 and 70 inclusive",
            field_errors={"cycle_used_hours": ["Must be between 0 and 70"]},
        )
    return hours_to_seconds(value)


def create_trip_plan(payload: dict[str, Any]) -> tuple[TripPlan, str]:
    """Validate → route → schedule → validate → persist. Returns plan and raw token."""
    current_label, current_coords = _parse_location(payload.get("current_location"), "current_location")
    pickup_label, pickup_coords = _parse_location(payload.get("pickup_location"), "pickup_location")
    dropoff_label, dropoff_coords = _parse_location(payload.get("dropoff_location"), "dropoff_location")
    cycle_used_s = _parse_cycle_hours(payload.get("cycle_used_hours"))

    tz_name = payload.get("home_terminal_tz") or "America/Chicago"
    try:
        tz = ZoneInfo(tz_name)
    except Exception as exc:
        raise PlanError(
            "Invalid home-terminal timezone",
            field_errors={"home_terminal_tz": ["Unknown timezone"]},
        ) from exc

    dep_raw = payload.get("departure_local")
    if not dep_raw:
        raise PlanError(
            "Departure date and time is required",
            field_errors={"departure_local": ["Required"]},
        )
    try:
        departure = datetime.fromisoformat(str(dep_raw).replace("Z", "+00:00"))
        if departure.tzinfo is None:
            departure = departure.replace(tzinfo=tz)
        else:
            departure = departure.astimezone(tz)
    except ValueError as exc:
        raise PlanError(
            "Invalid departure datetime",
            field_errors={"departure_local": ["Use ISO-8601 datetime"]},
        ) from exc

    miles_since = payload.get("miles_since_fuel", 0)
    try:
        miles_since_f = float(miles_since)
    except (TypeError, ValueError) as exc:
        raise PlanError(
            "Invalid miles since fuel",
            field_errors={"miles_since_fuel": ["Must be a number"]},
        ) from exc
    if miles_since_f < 0 or miles_since_f > 1000:
        raise PlanError(
            "Miles since fuel must be between 0 and 1000",
            field_errors={"miles_since_fuel": ["Must be between 0 and 1000"]},
        )
    miles_since_fuel_m = int(round(miles_since_f * 1609.344))

    fuel_minutes = payload.get("fuel_duration_minutes", 30)
    try:
        fuel_duration_s = int(float(fuel_minutes) * 60)
    except (TypeError, ValueError) as exc:
        raise PlanError("Invalid fuel duration", field_errors={"fuel_duration_minutes": ["Invalid"]}) from exc

    rest_status_raw = (payload.get("rest_status") or "OFF").upper()
    if rest_status_raw not in ("OFF", "SB"):
        raise PlanError("rest_status must be OFF or SB", field_errors={"rest_status": ["Invalid"]})
    sleeper = bool(payload.get("sleeper_equipped", False))
    if rest_status_raw == "SB" and not sleeper:
        raise PlanError(
            "Sleeper berth requires sleeper_equipped",
            field_errors={"rest_status": ["Enable sleeper berth equipped"]},
        )

    plan_settings = PlanningSettings(
        departure_local=departure,
        home_terminal_tz=tz_name,
        miles_since_fuel_m=miles_since_fuel_m,
        fuel_duration_s=fuel_duration_s,
        include_pretrip_inspection=bool(payload.get("include_pretrip_inspection", False)),
        rest_status=DutyStatus.SB if rest_status_raw == "SB" else DutyStatus.OFF,
        sleeper_equipped=sleeper,
        cycle_used_s=cycle_used_s,
        driver_name=payload.get("driver_name") or None,
        carrier_name=payload.get("carrier_name") or None,
        main_office=payload.get("main_office") or None,
        home_terminal=payload.get("home_terminal") or None,
        tractor_trailer=payload.get("tractor_trailer") or None,
        co_driver=payload.get("co_driver") or None,
        shipping_document=payload.get("shipping_document") or None,
        shipper_commodity=payload.get("shipper_commodity") or None,
        starting_odometer=payload.get("starting_odometer"),
    )

    provider = get_provider()
    try:
        leg1 = provider.route(
            current_coords,
            pickup_coords,
            from_label=current_label,
            to_label=pickup_label,
            leg_id="current_to_pickup",
        )
        leg2 = provider.route(
            pickup_coords,
            dropoff_coords,
            from_label=pickup_label,
            to_label=dropoff_label,
            leg_id="pickup_to_dropoff",
        )
    except QuotaExceeded as exc:
        raise PlanError(exc.message, code=exc.code, status=429, retryable=True) from exc
    except NoRouteFound as exc:
        raise PlanError(exc.message, code=exc.code, status=400, retryable=False) from exc
    except ProviderError as exc:
        status = 503 if exc.retryable else 502
        if exc.status and exc.status >= 500:
            status = 503
        raise PlanError(exc.message, code=exc.code, status=status, retryable=exc.retryable) from exc

    try:
        schedule = schedule_trip([leg1, leg2], plan_settings, validate=True)
    except DstUnsupportedError as exc:
        raise PlanError(str(exc), code="DST_TRANSITION_UNSUPPORTED", status=400) from exc
    except UnsupportedTripError as exc:
        raise PlanError(str(exc), code=exc.code, status=400) from exc

    if not schedule.validation.ok:
        raise PlanError(
            "Generated schedule failed independent validation",
            code="VALIDATION_FAILED",
            status=500,
            field_errors={"validation": list(schedule.validation.errors)},
        )

    logs = project_daily_logs(
        schedule.events,
        plan_settings,
        origin_label=current_label,
        destination_label=dropoff_label,
    )

    token = TripPlan.mint_token()
    plan = TripPlan.objects.create(
        access_token_hash=TripPlan.hash_token(token),
        schema_version=SCHEMA_VERSION,
        rule_version=RULE_VERSION,
        input_json=payload,
        route_json={
            "legs": [leg_to_dict(leg1), leg_to_dict(leg2)],
            "profile": "driving-hgv",
            "note": (
                "HGV routing used. Unspecified vehicle dimensions and incomplete map "
                "restrictions prevent a guarantee of truck suitability."
            ),
        },
        timeline_json=[event_to_dict(e) for e in schedule.events],
        logs_json=[log_to_dict(s) for s in logs],
        diagnostics_json=schedule.diagnostics,
        validation_json={
            "ok": schedule.validation.ok,
            "errors": list(schedule.validation.errors),
            "warnings": list(schedule.validation.warnings),
            "label": "Within modeled limits" if schedule.validation.ok else "Validation failed",
        },
        provider_meta={
            "provider": leg1.provider,
            "profile": leg1.profile,
            "route_version": leg1.route_version,
        },
    )
    return plan, token


def plan_to_response(plan: TripPlan, *, include_token: str | None = None) -> dict[str, Any]:
    data = {
        "id": str(plan.id),
        "created_at": plan.created_at.isoformat(),
        "schema_version": plan.schema_version,
        "rule_version": plan.rule_version,
        "input": plan.input_json,
        "route": plan.route_json,
        "timeline": plan.timeline_json,
        "daily_logs": plan.logs_json,
        "diagnostics": plan.diagnostics_json,
        "validation": plan.validation_json,
        "provider": plan.provider_meta,
        "assumptions": {
            "cycle_mode": "Conservative cycle estimate",
            "property_carrying": True,
            "cycle": "70 hours / 8 days",
            "fuel_interval_miles": 1000,
            "pickup_dropoff_hours": 1,
            "fresh_shift": True,
            "banner": "Planned driver log — not a certified ELD record.",
        },
        "map": {
            "tile_url": settings.MAP_TILE_URL,
            "attribution": settings.MAP_TILE_ATTRIBUTION,
        },
    }
    if include_token:
        data["access_token"] = include_token
    return data
