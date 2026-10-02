"""Helpers for building synthetic route legs in tests."""

from __future__ import annotations

from datetime import datetime, timezone

from trips.domain.types import Coordinates, RouteLeg, RouteStep


def make_leg(
    *,
    leg_id: str,
    from_label: str,
    to_label: str,
    duration_s: int,
    distance_m: int,
    start: Coordinates,
    end: Coordinates | None = None,
) -> RouteLeg:
    end = end or start
    geometry = ((start.lon, start.lat), (end.lon, end.lat))
    step = RouteStep(
        distance_m=distance_m,
        duration_s=duration_s,
        instruction=f"Drive to {to_label}",
        geometry_lon_lat=geometry,
    )
    return RouteLeg(
        leg_id=leg_id,
        from_label=from_label,
        to_label=to_label,
        distance_m=distance_m,
        duration_s=duration_s,
        steps=(step,),
        geometry_lon_lat=geometry,
        provider="test",
        profile="driving-hgv",
        fetched_at=datetime.now(timezone.utc),
        route_version="test-v1",
    )


def miles(n: float) -> int:
    return int(round(n * 1609.344))
