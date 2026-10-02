"""Typed domain records for RouteLedger scheduling."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class DutyStatus(str, Enum):
    OFF = "OFF"
    SB = "SB"
    D = "D"
    ON = "ON"


class EventType(str, Enum):
    INSPECTION = "INSPECTION"
    DRIVING = "DRIVING"
    PICKUP = "PICKUP"
    DROPOFF = "DROPOFF"
    FUEL = "FUEL"
    BREAK = "BREAK"
    REST = "REST"
    RESTART = "RESTART"
    ASSUMED_OFF = "ASSUMED_OFF"
    MARKER = "MARKER"


class ReasonCode(str, Enum):
    PICKUP = "PICKUP"
    DROPOFF = "DROPOFF"
    FUEL_INTERVAL = "FUEL_INTERVAL"
    BREAK_AFTER_DRIVING = "BREAK_AFTER_DRIVING"
    SHIFT_DRIVING_LIMIT = "SHIFT_DRIVING_LIMIT"
    SHIFT_WINDOW_LIMIT = "SHIFT_WINDOW_LIMIT"
    CYCLE_LIMIT = "CYCLE_LIMIT"
    CYCLE_RESTART = "CYCLE_RESTART"
    INSPECTION = "INSPECTION"
    DAILY_REST = "DAILY_REST"
    ROUTE_LEG = "ROUTE_LEG"
    PLANNING_FILLER = "PLANNING_FILLER"


class LocationProvenance(str, Enum):
    USER_SELECTED = "USER_SELECTED"
    ROUTE_INTERPOLATED = "ROUTE_INTERPOLATED"
    PLANNED_UNVERIFIED = "PLANNED_UNVERIFIED"
    IDENTICAL = "IDENTICAL"


@dataclass(frozen=True)
class Coordinates:
    """WGS84 coordinates stored as latitude, longitude."""

    lat: float
    lon: float

    def as_lon_lat(self) -> tuple[float, float]:
        return (self.lon, self.lat)

    def as_lat_lon(self) -> tuple[float, float]:
        return (self.lat, self.lon)


@dataclass(frozen=True)
class Location:
    label: str
    coordinates: Coordinates
    country_code: str = "US"
    region: str | None = None
    locality: str | None = None
    provenance: LocationProvenance = LocationProvenance.USER_SELECTED


@dataclass(frozen=True)
class RouteStep:
    """One provider step with geometry in [lon, lat] GeoJSON order."""

    distance_m: int
    duration_s: int
    instruction: str
    geometry_lon_lat: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class RouteLeg:
    """A road leg between two waypoints."""

    leg_id: str
    from_label: str
    to_label: str
    distance_m: int
    duration_s: int
    steps: tuple[RouteStep, ...]
    geometry_lon_lat: tuple[tuple[float, float], ...]
    provider: str
    profile: str
    fetched_at: datetime
    route_version: str


@dataclass(frozen=True)
class ClockSnapshot:
    shift_driving_s: int
    shift_elapsed_s: int
    driving_since_break_s: int
    cycle_used_s: int
    miles_since_fuel_m: int
    continuous_rest_s: int


@dataclass(frozen=True)
class TimelineEvent:
    """Half-open interval [start_utc, end_utc)."""

    event_id: str
    event_type: EventType
    status: DutyStatus
    start_utc: datetime
    end_utc: datetime
    duration_s: int
    reason_codes: tuple[ReasonCode, ...]
    clocks_at_start: ClockSnapshot
    clocks_at_end: ClockSnapshot
    start_progress_m: int = 0
    end_progress_m: int = 0
    distance_m: int = 0
    start_coord: Coordinates | None = None
    end_coord: Coordinates | None = None
    location_label: str | None = None
    location_provenance: LocationProvenance | None = None
    leg_id: str | None = None
    explanation: str = ""


@dataclass(frozen=True)
class PlanningSettings:
    departure_local: datetime  # timezone-aware in home terminal zone
    home_terminal_tz: str
    miles_since_fuel_m: int = 0
    fuel_duration_s: int = 30 * 60
    include_pretrip_inspection: bool = False
    rest_status: DutyStatus = DutyStatus.OFF
    sleeper_equipped: bool = False
    cycle_used_s: int = 0
    # Optional identity fields
    driver_name: str | None = None
    carrier_name: str | None = None
    main_office: str | None = None
    home_terminal: str | None = None
    tractor_trailer: str | None = None
    co_driver: str | None = None
    shipping_document: str | None = None
    shipper_commodity: str | None = None
    starting_odometer: int | None = None


@dataclass(frozen=True)
class DriverState:
    """Initial driver state at departure."""

    cycle_used_s: int
    shift_driving_s: int = 0
    shift_elapsed_s: int = 0
    driving_since_break_s: int = 0
    miles_since_fuel_m: int = 0
    continuous_rest_s: int = 10 * 3600
    shift_window_open: bool = False
    fresh_shift: bool = True


@dataclass(frozen=True)
class StatusSegment:
    status: DutyStatus
    start_s: int  # seconds since midnight [0, 86400)
    end_s: int
    event_id: str
    is_planning_filler: bool = False


@dataclass(frozen=True)
class Remark:
    time_local: datetime
    text: str
    location_label: str | None = None
    event_id: str | None = None
    estimated: bool = False


@dataclass(frozen=True)
class DailyLogSheet:
    date_local: date
    from_label: str
    to_label: str
    timezone: str
    utc_offset: str
    driving_miles: float
    total_miles: float
    segments: tuple[StatusSegment, ...]
    totals_s: dict[str, int]
    remarks: tuple[Remark, ...]
    recap: dict[str, Any]
    page_number: int
    total_pages: int
    carrier_name: str | None = None
    main_office: str | None = None
    home_terminal: str | None = None
    tractor_trailer: str | None = None
    driver_name: str | None = None
    co_driver: str | None = None
    shipping_document: str | None = None
    shipper_commodity: str | None = None
    planned_banner: str = "Planned driver log — not a certified ELD record."


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScheduleResult:
    events: tuple[TimelineEvent, ...]
    diagnostics: dict[str, Any] = field(default_factory=dict)
    validation: ValidationResult = field(
        default_factory=lambda: ValidationResult(ok=False, errors=("not validated",))
    )
    daily_logs: tuple[DailyLogSheet, ...] = ()
