"""API tests using the fake provider."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture(autouse=True)
def _fake_provider(settings):
    settings.USE_FAKE_PROVIDER = True


def test_health(api):
    r = api.get("/api/health/")
    assert r.status_code == 200
    assert r.data["status"] == "ok"


def test_location_search(api):
    r = api.get("/api/locations/search/", {"q": "chicago"})
    assert r.status_code == 200
    assert len(r.data["results"]) >= 1
    assert "coordinates" in r.data["results"][0]


def test_create_and_get_trip(api):
    payload = {
        "current_location": {
            "label": "Chicago, Illinois, United States",
            "coordinates": {"lat": 41.8781, "lon": -87.6298},
        },
        "pickup_location": {
            "label": "Joliet, Illinois, United States",
            "coordinates": {"lat": 41.525, "lon": -88.0817},
        },
        "dropoff_location": {
            "label": "Bloomington, Illinois, United States",
            "coordinates": {"lat": 40.4842, "lon": -88.9937},
        },
        "cycle_used_hours": 0,
        "departure_local": "2026-06-15T08:00:00-05:00",
        "home_terminal_tz": "America/Chicago",
        "miles_since_fuel": 0,
    }
    r = api.post("/api/trips/", payload, format="json")
    assert r.status_code == 201, r.data
    assert "access_token" in r.data
    assert r.data["validation"]["ok"] is True
    assert len(r.data["timeline"]) >= 4
    assert len(r.data["daily_logs"]) >= 1
    trip_id = r.data["id"]
    token = r.data["access_token"]

    bad = api.get(f"/api/trips/{trip_id}/")
    assert bad.status_code == 401

    wrong = api.get(f"/api/trips/{trip_id}/", HTTP_AUTHORIZATION="Bearer wrong")
    assert wrong.status_code == 404

    good = api.get(f"/api/trips/{trip_id}/", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert good.status_code == 200
    assert good.data["id"] == trip_id
    assert "access_token" not in good.data


def test_cycle_validation(api):
    payload = {
        "current_location": {
            "label": "Chicago, IL",
            "coordinates": {"lat": 41.8781, "lon": -87.6298},
        },
        "pickup_location": {
            "label": "Joliet, IL",
            "coordinates": {"lat": 41.525, "lon": -88.0817},
        },
        "dropoff_location": {
            "label": "Bloomington, IL",
            "coordinates": {"lat": 40.4842, "lon": -88.9937},
        },
        "cycle_used_hours": 71,
        "departure_local": "2026-06-15T08:00:00-05:00",
        "home_terminal_tz": "America/Chicago",
    }
    r = api.post("/api/trips/", payload, format="json")
    assert r.status_code == 400
    assert r.data["code"] == "PLAN_ERROR" or "cycle" in r.data["message"].lower() or r.data.get("field_errors")


def test_provider_quota(api, monkeypatch):
    from trips.providers.fake import FakeRoutingProvider
    from trips.services import planning

    monkeypatch.setattr(planning, "get_provider", lambda: FakeRoutingProvider(fail_mode="quota"))
    payload = {
        "current_location": {
            "label": "Chicago, IL",
            "coordinates": {"lat": 41.8781, "lon": -87.6298},
        },
        "pickup_location": {
            "label": "Joliet, IL",
            "coordinates": {"lat": 41.525, "lon": -88.0817},
        },
        "dropoff_location": {
            "label": "Bloomington, IL",
            "coordinates": {"lat": 40.4842, "lon": -88.9937},
        },
        "cycle_used_hours": 0,
        "departure_local": "2026-06-15T08:00:00-05:00",
        "home_terminal_tz": "America/Chicago",
    }
    r = api.post("/api/trips/", payload, format="json")
    assert r.status_code == 429
    assert r.data["retryable"] is True
