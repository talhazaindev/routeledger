"""URL routes for trips API."""

from django.urls import path

from trips.api.views import create_trip, get_trip, health, location_search

urlpatterns = [
    path("health/", health, name="health"),
    path("locations/search/", location_search, name="location-search"),
    path("trips/", create_trip, name="trip-create"),
    path("trips/<uuid:trip_id>/", get_trip, name="trip-detail"),
]
