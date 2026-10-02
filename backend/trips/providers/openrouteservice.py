"""OpenRouteService (HeiGIT) adapter — driving-hgv only."""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from django.conf import settings
from django.core.cache import cache

from trips.domain.constants import CONTIGUOUS_US_LAT, CONTIGUOUS_US_LON
from trips.domain.types import Coordinates, Location, LocationProvenance, RouteLeg, RouteStep
from trips.providers.base import GeocodeResult, NoRouteFound, ProviderError, QuotaExceeded

logger = logging.getLogger(__name__)

PROVIDER_NAME = "openrouteservice-heigit"
PROVIDER_VERSION = "v2"
PROFILE = "driving-hgv"


class OpenRouteServiceProvider:
    """HeiGIT api.heigit.org client. API key never leaves the server."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_s: float | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.ORS_API_KEY
        self.base_url = (base_url or settings.ORS_BASE_URL).rstrip("/")
        self.timeout_s = timeout_s if timeout_s is not None else settings.ORS_TIMEOUT_S
        if not self.api_key:
            raise ProviderError(
                "OPENROUTESERVICE_API_KEY is not configured",
                code="MISSING_API_KEY",
                retryable=False,
            )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        retries: int = 2,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                with httpx.Client(timeout=self.timeout_s) as client:
                    resp = client.request(
                        method, url, headers=self._headers(), params=params, json=json_body
                    )
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    if attempt < retries and retry_after:
                        time.sleep(min(float(retry_after), 5.0))
                        continue
                    raise QuotaExceeded()
                if resp.status_code >= 500:
                    raise ProviderError(
                        "Upstream routing service unavailable",
                        code="UPSTREAM_UNAVAILABLE",
                        retryable=True,
                        status=resp.status_code,
                    )
                if resp.status_code >= 400:
                    detail = resp.text[:300]
                    if "could not find routable point" in detail.lower() or resp.status_code == 404:
                        raise NoRouteFound()
                    raise ProviderError(
                        f"Upstream error: {detail}",
                        code="UPSTREAM_ERROR",
                        retryable=False,
                        status=resp.status_code,
                    )
                return resp.json()
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_err = exc
                if attempt < retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise ProviderError(
                    "Upstream routing timeout",
                    code="UPSTREAM_TIMEOUT",
                    retryable=True,
                    status=504,
                ) from exc
        raise ProviderError(str(last_err or "request failed"), retryable=True)

    def search(self, query: str, *, limit: int = 5) -> list[GeocodeResult]:
        q = query.strip()
        if len(q) < 2:
            return []
        cache_key = f"geo:v1:{hashlib.sha256(q.lower().encode()).hexdigest()}:{limit}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        data = self._request(
            "GET",
            "/geocode/autocomplete",
            params={
                "text": q,
                "size": limit,
                "boundary.country": "US",
                "layers": "locality,borough,county,neighbourhood,address",
            },
        )
        results: list[GeocodeResult] = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            coords = geom.get("coordinates") or []
            if len(coords) < 2:
                continue
            lon, lat = float(coords[0]), float(coords[1])
            if not _in_contiguous_us(lat, lon):
                continue
            country = (props.get("country_a") or props.get("country_code") or "US").upper()
            if country not in ("US", "USA"):
                continue
            label = props.get("label") or props.get("name") or q
            loc = Location(
                label=label,
                coordinates=Coordinates(lat=lat, lon=lon),
                country_code="US",
                region=props.get("region") or props.get("region_a"),
                locality=props.get("locality") or props.get("name"),
                provenance=LocationProvenance.USER_SELECTED,
            )
            conf = float(props.get("confidence") or 0.5)
            results.append(GeocodeResult(location=loc, confidence=conf))

        cache.set(cache_key, results, timeout=3600)
        return results

    def route(
        self,
        origin: Coordinates,
        destination: Coordinates,
        *,
        from_label: str,
        to_label: str,
        leg_id: str,
    ) -> RouteLeg:
        if (
            abs(origin.lat - destination.lat) < 1e-7
            and abs(origin.lon - destination.lon) < 1e-7
        ):
            now = datetime.now(timezone.utc)
            return RouteLeg(
                leg_id=leg_id,
                from_label=from_label,
                to_label=to_label,
                distance_m=0,
                duration_s=0,
                steps=(),
                geometry_lon_lat=((origin.lon, origin.lat),),
                provider=PROVIDER_NAME,
                profile=PROFILE,
                fetched_at=now,
                route_version=PROVIDER_VERSION,
            )

        cache_key = (
            f"route:v1:{PROFILE}:{origin.lat:.5f},{origin.lon:.5f}:"
            f"{destination.lat:.5f},{destination.lon:.5f}"
        )
        cached = cache.get(cache_key)
        if cached is not None:
            return RouteLeg(
                leg_id=leg_id,
                from_label=from_label,
                to_label=to_label,
                distance_m=cached.distance_m,
                duration_s=cached.duration_s,
                steps=cached.steps,
                geometry_lon_lat=cached.geometry_lon_lat,
                provider=cached.provider,
                profile=cached.profile,
                fetched_at=cached.fetched_at,
                route_version=cached.route_version,
            )

        body = {
            "coordinates": [list(origin.as_lon_lat()), list(destination.as_lon_lat())],
            "instructions": True,
            "geometry": True,
            "elevation": False,
        }
        data = self._request(
            "POST",
            f"/v2/directions/{PROFILE}/geojson",
            json_body=body,
        )
        features = data.get("features") or []
        if not features:
            raise NoRouteFound()
        feature = features[0]
        props = feature.get("properties") or {}
        summary = props.get("summary") or {}
        distance_m = int(round(float(summary.get("distance") or 0)))
        duration_s = int(round(float(summary.get("duration") or 0)))
        geometry = feature.get("geometry") or {}
        coords_raw = geometry.get("coordinates") or []
        geometry_lon_lat = tuple(
            (float(c[0]), float(c[1])) for c in coords_raw if len(c) >= 2
        )
        segments = props.get("segments") or []
        steps: list[RouteStep] = []
        for seg in segments:
            for step in seg.get("steps") or []:
                way_pts = step.get("way_points") or [0, 0]
                i0, i1 = int(way_pts[0]), int(way_pts[1])
                step_geom = geometry_lon_lat[i0 : i1 + 1] if geometry_lon_lat else ()
                steps.append(
                    RouteStep(
                        distance_m=int(round(float(step.get("distance") or 0))),
                        duration_s=int(round(float(step.get("duration") or 0))),
                        instruction=str(step.get("instruction") or ""),
                        geometry_lon_lat=tuple(step_geom),
                    )
                )

        now = datetime.now(timezone.utc)
        leg = RouteLeg(
            leg_id=leg_id,
            from_label=from_label,
            to_label=to_label,
            distance_m=distance_m,
            duration_s=duration_s,
            steps=tuple(steps),
            geometry_lon_lat=geometry_lon_lat,
            provider=PROVIDER_NAME,
            profile=PROFILE,
            fetched_at=now,
            route_version=PROVIDER_VERSION,
        )
        cache.set(cache_key, leg, timeout=3600)
        return leg


def _in_contiguous_us(lat: float, lon: float) -> bool:
    return (
        CONTIGUOUS_US_LAT[0] <= lat <= CONTIGUOUS_US_LAT[1]
        and CONTIGUOUS_US_LON[0] <= lon <= CONTIGUOUS_US_LON[1]
    )
