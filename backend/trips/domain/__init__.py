"""Pure domain package for RouteLedger HOS scheduling."""

from .constants import RULE_VERSION, SCHEMA_VERSION
from .logs import project_daily_logs
from .scheduler import DstUnsupportedError, UnsupportedTripError, hours_to_seconds, schedule_trip
from .types import (
    DailyLogSheet,
    DutyStatus,
    PlanningSettings,
    RouteLeg,
    RouteStep,
    ScheduleResult,
    TimelineEvent,
)
from .validator import mutate_for_tests, validate_timeline

__all__ = [
    "RULE_VERSION",
    "SCHEMA_VERSION",
    "DailyLogSheet",
    "DstUnsupportedError",
    "DutyStatus",
    "PlanningSettings",
    "RouteLeg",
    "RouteStep",
    "ScheduleResult",
    "TimelineEvent",
    "UnsupportedTripError",
    "hours_to_seconds",
    "mutate_for_tests",
    "project_daily_logs",
    "schedule_trip",
    "validate_timeline",
]
