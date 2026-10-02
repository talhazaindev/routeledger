"""Routing provider protocol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from trips.domain.types import Coordinates, Location, RouteLeg


@dataclass(frozen=True)
class GeocodeResult:
    location: Location
    confidence: float = 1.0


class RoutingProvider(Protocol):
    """Adapter interface for hosted routing / geocoding."""

    def search(self, query: str, *, limit: int = 5) -> list[GeocodeResult]:
        """Autocomplete-capable location search."""

    def route(
        self,
        origin: Coordinates,
        destination: Coordinates,
        *,
        from_label: str,
        to_label: str,
        leg_id: str,
    ) -> RouteLeg:
        """Fetch a driving-hgv road leg. Zero-length identical points must work."""


class ProviderError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "PROVIDER_ERROR",
        retryable: bool = False,
        status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable
        self.status = status


class QuotaExceeded(ProviderError):
    def __init__(self, message: str = "Upstream routing quota exceeded") -> None:
        super().__init__(message, code="QUOTA_EXCEEDED", retryable=True, status=429)


class NoRouteFound(ProviderError):
    def __init__(self, message: str = "No road route found between locations") -> None:
        super().__init__(message, code="NO_ROUTE", retryable=False, status=400)
