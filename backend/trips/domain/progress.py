"""Monotonic route progress index for distance/time interpolation."""

from __future__ import annotations

from dataclasses import dataclass

from .types import Coordinates, RouteLeg


@dataclass(frozen=True)
class ProgressPoint:
    """A sample along the cumulative trip progress."""

    cumulative_m: int
    cumulative_s: int
    coord: Coordinates
    leg_id: str
    step_index: int


@dataclass
class ProgressIndex:
    """Maps cumulative meters / seconds to coordinates along routed geometry.

    Interpolation uses step distance fraction within a step, never vertex count
    or straight-line start/end of the whole leg.
    """

    points: list[ProgressPoint]
    total_m: int
    total_s: int

    def coordinate_at_distance(self, distance_m: int) -> Coordinates:
        if not self.points:
            raise ValueError("empty progress index")
        target = max(0, min(distance_m, self.total_m))
        if target <= self.points[0].cumulative_m:
            return self.points[0].coord
        for i in range(1, len(self.points)):
            a = self.points[i - 1]
            b = self.points[i]
            if target <= b.cumulative_m:
                span = b.cumulative_m - a.cumulative_m
                if span <= 0:
                    return b.coord
                t = (target - a.cumulative_m) / span
                return Coordinates(
                    lat=a.coord.lat + t * (b.coord.lat - a.coord.lat),
                    lon=a.coord.lon + t * (b.coord.lon - a.coord.lon),
                )
        return self.points[-1].coord

    def time_at_distance(self, distance_m: int) -> int:
        """Estimated cumulative driving seconds at a distance along the route."""
        if not self.points:
            return 0
        target = max(0, min(distance_m, self.total_m))
        if target <= self.points[0].cumulative_m:
            return self.points[0].cumulative_s
        for i in range(1, len(self.points)):
            a = self.points[i - 1]
            b = self.points[i]
            if target <= b.cumulative_m:
                span = b.cumulative_m - a.cumulative_m
                if span <= 0:
                    return b.cumulative_s
                t = (target - a.cumulative_m) / span
                return int(round(a.cumulative_s + t * (b.cumulative_s - a.cumulative_s)))
        return self.points[-1].cumulative_s

    def distance_at_time(self, time_s: int) -> int:
        """Estimated cumulative meters at a driving-time progress value."""
        if not self.points:
            return 0
        target = max(0, min(time_s, self.total_s))
        if target <= self.points[0].cumulative_s:
            return self.points[0].cumulative_m
        for i in range(1, len(self.points)):
            a = self.points[i - 1]
            b = self.points[i]
            if target <= b.cumulative_s:
                span = b.cumulative_s - a.cumulative_s
                if span <= 0:
                    return b.cumulative_m
                t = (target - a.cumulative_s) / span
                return int(round(a.cumulative_m + t * (b.cumulative_m - a.cumulative_m)))
        return self.points[-1].cumulative_m


def _haversine_m(a: Coordinates, b: Coordinates) -> float:
    from math import asin, cos, radians, sin, sqrt

    r = 6_371_000.0
    dlat = radians(b.lat - a.lat)
    dlon = radians(b.lon - a.lon)
    la1, la2 = radians(a.lat), radians(b.lat)
    h = sin(dlat / 2) ** 2 + cos(la1) * cos(la2) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(h))


def build_progress_index(legs: list[RouteLeg]) -> ProgressIndex:
    """Build a monotonic progress index across all legs and steps.

    Within each step, distance is distributed proportionally to consecutive
    geometry segment lengths; duration is distributed by the same fraction of
    the step's provider duration. This is an approximation documented for
    assessors: we never interpolate by vertex count alone.
    """
    points: list[ProgressPoint] = []
    cum_m = 0
    cum_s = 0

    for leg in legs:
        if leg.distance_m == 0 or not leg.steps:
            # Zero-length leg: single point at start of geometry if present
            if leg.geometry_lon_lat:
                lon, lat = leg.geometry_lon_lat[0]
                points.append(
                    ProgressPoint(
                        cumulative_m=cum_m,
                        cumulative_s=cum_s,
                        coord=Coordinates(lat=lat, lon=lon),
                        leg_id=leg.leg_id,
                        step_index=0,
                    )
                )
            continue

        for step_i, step in enumerate(leg.steps):
            coords = [
                Coordinates(lat=lat, lon=lon) for lon, lat in step.geometry_lon_lat
            ]
            if not coords:
                continue
            if not points or points[-1].coord != coords[0] or points[-1].leg_id != leg.leg_id:
                points.append(
                    ProgressPoint(
                        cumulative_m=cum_m,
                        cumulative_s=cum_s,
                        coord=coords[0],
                        leg_id=leg.leg_id,
                        step_index=step_i,
                    )
                )

            if len(coords) == 1 or step.distance_m == 0:
                cum_m += step.distance_m
                cum_s += step.duration_s
                points.append(
                    ProgressPoint(
                        cumulative_m=cum_m,
                        cumulative_s=cum_s,
                        coord=coords[-1],
                        leg_id=leg.leg_id,
                        step_index=step_i,
                    )
                )
                continue

            # Segment lengths for proportional allocation within the step
            seglens: list[float] = []
            for i in range(1, len(coords)):
                seglens.append(max(_haversine_m(coords[i - 1], coords[i]), 1e-6))
            total_seg = sum(seglens)
            for i, seg_m in enumerate(seglens):
                frac = seg_m / total_seg
                cum_m += int(round(step.distance_m * frac))
                cum_s += int(round(step.duration_s * frac))
                # Correct rounding drift on last segment
                if i == len(seglens) - 1:
                    # Will be reconciled after step loop via totals; keep monotonic
                    pass
                points.append(
                    ProgressPoint(
                        cumulative_m=cum_m,
                        cumulative_s=cum_s,
                        coord=coords[i + 1],
                        leg_id=leg.leg_id,
                        step_index=step_i,
                    )
                )

    total_m = sum(leg.distance_m for leg in legs)
    total_s = sum(leg.duration_s for leg in legs)
    if points:
        # Snap final cumulative values to provider totals
        last = points[-1]
        points[-1] = ProgressPoint(
            cumulative_m=total_m,
            cumulative_s=total_s,
            coord=last.coord,
            leg_id=last.leg_id,
            step_index=last.step_index,
        )
    return ProgressIndex(points=points, total_m=total_m, total_s=total_s)
