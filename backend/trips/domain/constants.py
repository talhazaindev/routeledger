"""Hours-of-service and planning constants (integer seconds / meters)."""

from __future__ import annotations

# Duty limits
SHIFT_DRIVING_LIMIT_S = 11 * 3600
SHIFT_WINDOW_LIMIT_S = 14 * 3600
BREAK_DRIVING_LIMIT_S = 8 * 3600
BREAK_REQUIRED_S = 30 * 60
DAILY_REST_S = 10 * 3600
CYCLE_RESTART_S = 34 * 3600
CYCLE_LIMIT_S = 70 * 3600
CYCLE_WINDOW_DAYS = 8

# Service durations
PICKUP_DURATION_S = 3600
DROPOFF_DURATION_S = 3600
DEFAULT_FUEL_DURATION_S = 30 * 60
INSPECTION_DURATION_S = 15 * 60

# Fuel
FUEL_INTERVAL_M = 1_609_344  # 1000 miles in meters
METERS_PER_MILE = 1609.344

# Planning bounds
MAX_PLAN_DAYS = 21
MAX_EVENTS = 400
SECONDS_PER_DAY = 86_400

RULE_VERSION = "hos-property-carrying-70-8-v1"
SCHEMA_VERSION = "trip-plan-v1"

# Contiguous US approximate bounds (excluding AK/HI)
CONTIGUOUS_US_LAT = (24.0, 49.5)
CONTIGUOUS_US_LON = (-125.0, -66.0)
