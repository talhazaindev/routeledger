"""Deterministic fake provider for tests and labeled demo mode."""

from __future__ import annotations

from datetime import datetime, timezone

from trips.domain.types import Coordinates, Location, LocationProvenance, RouteLeg, RouteStep
from trips.providers.base import GeocodeResult, NoRouteFound, ProviderError, QuotaExceeded

CITIES: dict[str, tuple[str, Coordinates, str]] = {
    "chicago": ("Chicago, Illinois, United States", Coordinates(41.8781, -87.6298), "IL"),
    "joliet": ("Joliet, Illinois, United States", Coordinates(41.5250, -88.0817), "IL"),
    "bloomington": ("Bloomington, Illinois, United States", Coordinates(40.4842, -88.9937), "IL"),
    "indianapolis": ("Indianapolis, Indiana, United States", Coordinates(39.7684, -86.1581), "IN"),
    "denver": ("Denver, Colorado, United States", Coordinates(39.7392, -104.9903), "CO"),
    "kansas city": ("Kansas City, Missouri, United States", Coordinates(39.0997, -94.5786), "MO"),
}


class FakeRoutingProvider:
    """Offline fixtures — clearly labeled demo/test only."""

    def __init__(self, *, fail_mode: str | None = None) -> None:
        self.fail_mode = fail_mode

    def search(self, query: str, *, limit: int = 5) -> list[GeocodeResult]:
        if self.fail_mode == "timeout":
            raise ProviderError("timeout", code="UPSTREAM_TIMEOUT", retryable=True, status=504)
        if self.fail_mode == "quota":
            raise QuotaExceeded()
        q = query.lower().strip()
        results: list[GeocodeResult] = []
        for key, (label, coords, region) in CITIES.items():
            if key in q or q in key or q in label.lower():
                results.append(
                    GeocodeResult(
                        location=Location(
                            label=label,
                            coordinates=coords,
                            country_code="US",
                            region=region,
                            locality=label.split(",")[0],
                            provenance=LocationProvenance.USER_SELECTED,
                        ),
                        confidence=0.9,
                    )
                )
        return results[:limit]

    def route(
        self,
        origin: Coordinates,
        destination: Coordinates,
        *,
        from_label: str,
        to_label: str,
        leg_id: str,
    ) -> RouteLeg:
        if self.fail_mode == "timeout":
            raise ProviderError("timeout", code="UPSTREAM_TIMEOUT", retryable=True, status=504)
        if self.fail_mode == "quota":
            raise QuotaExceeded()
        if self.fail_mode == "no_route":
            raise NoRouteFound()

        if abs(origin.lat - destination.lat) < 1e-7 and abs(origin.lon - destination.lon) < 1e-7:
            return RouteLeg(
                leg_id=leg_id,
                from_label=from_label,
                to_label=to_label,
                distance_m=0,
                duration_s=0,
                steps=(),
                geometry_lon_lat=((origin.lon, origin.lat),),
                provider="fake",
                profile="driving-hgv",
                fetched_at=datetime.now(timezone.utc),
                route_version="fake-v1",
            )

        from math import asin, cos, radians, sin, sqrt

        r = 6_371_000.0
        dlat = radians(destination.lat - origin.lat)
        dlon = radians(destination.lon - origin.lon)
        la1, la2 = radians(origin.lat), radians(destination.lat)
        h = sin(dlat / 2) ** 2 + cos(la1) * cos(la2) * sin(dlon / 2) ** 2
        straight = 2 * r * asin(sqrt(h))
        distance_m = int(straight * 1.3)
        duration_s = max(1, int(distance_m / (60 * 1609.344 / 3600)))
        geometry = ((origin.lon, origin.lat), (destination.lon, destination.lat))
        step = RouteStep(
            distance_m=distance_m,
            duration_s=duration_s,
            instruction=f"Drive toward {to_label}",
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
            provider="fake",
            profile="driving-hgv",
            fetched_at=datetime.now(timezone.utc),
            route_version="fake-v1",
        )
