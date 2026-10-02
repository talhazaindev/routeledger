"""API views."""

from __future__ import annotations

from django.http import JsonResponse
from rest_framework import status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from trips.api.errors import error_body
from trips.models import TripPlan
from trips.providers.base import ProviderError, QuotaExceeded
from trips.services.planning import PlanError, create_trip_plan, get_provider, plan_to_response


class LocationSearchThrottle(AnonRateThrottle):
    scope = "location_search"


class TripCreateThrottle(AnonRateThrottle):
    scope = "trip_create"


@api_view(["GET"])
def health(_request):
    return Response({"status": "ok", "service": "routeledger"})


@api_view(["GET"])
@throttle_classes([LocationSearchThrottle])
def location_search(request):
    q = (request.query_params.get("q") or "").strip()
    if len(q) < 2:
        return Response({"results": []})
    try:
        provider = get_provider()
        results = provider.search(q, limit=8)
    except QuotaExceeded as exc:
        return Response(
            error_body(code=exc.code, message=exc.message, retryable=True),
            status=429,
        )
    except ProviderError as exc:
        return Response(
            error_body(code=exc.code, message=exc.message, retryable=exc.retryable),
            status=503 if exc.retryable else 502,
        )
    return Response(
        {
            "results": [
                {
                    "label": r.location.label,
                    "coordinates": {
                        "lat": r.location.coordinates.lat,
                        "lon": r.location.coordinates.lon,
                    },
                    "region": r.location.region,
                    "locality": r.location.locality,
                    "country_code": r.location.country_code,
                    "confidence": r.confidence,
                }
                for r in results
            ]
        }
    )


@api_view(["POST"])
@throttle_classes([TripCreateThrottle])
def create_trip(request):
    try:
        plan, token = create_trip_plan(request.data if isinstance(request.data, dict) else {})
    except PlanError as exc:
        return Response(
            error_body(
                code=exc.code,
                message=exc.message,
                field_errors=exc.field_errors,
                retryable=exc.retryable,
            ),
            status=exc.status,
        )
    return Response(plan_to_response(plan, include_token=token), status=status.HTTP_201_CREATED)


@api_view(["GET"])
def get_trip(request, trip_id):
    auth = request.headers.get("Authorization") or ""
    token = ""
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    if not token:
        token = request.query_params.get("access_token") or ""
    if not token:
        return Response(
            error_body(code="UNAUTHORIZED", message="Access token required"),
            status=401,
        )
    try:
        plan = TripPlan.objects.get(pk=trip_id)
    except (TripPlan.DoesNotExist, ValueError):
        return Response(
            error_body(code="NOT_FOUND", message="Trip not found"),
            status=404,
        )
    if plan.access_token_hash != TripPlan.hash_token(token):
        return Response(
            error_body(code="NOT_FOUND", message="Trip not found"),
            status=404,
        )
    return Response(plan_to_response(plan))
