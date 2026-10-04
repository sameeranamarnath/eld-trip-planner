"""HTTP surface of the ELD trip planner."""

from __future__ import annotations

import logging

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from eld.serializers import TripPlanRequestSerializer
from eld.services.geocoding import get_geocoder
from eld.services.hos import DEFAULT_RULES
from eld.services.planner import TripPlanRequest, plan_trip

logger = logging.getLogger(__name__)

# Autocomplete sizing. The UI shows six rows; past ten the list stops being useful.
PLACES_DEFAULT_LIMIT = 6
PLACES_MAX_LIMIT = 10


def _requested_limit(raw: str | None) -> int:
    """Clamp the ``?limit=`` query parameter to a usable autocomplete size."""
    try:
        wanted = int(raw) if raw not in (None, "") else PLACES_DEFAULT_LIMIT
    except (TypeError, ValueError):
        wanted = PLACES_DEFAULT_LIMIT
    return max(1, min(wanted, PLACES_MAX_LIMIT))


class HealthView(APIView):
    """Cheap liveness probe that also reports the active providers."""

    def get(self, _request):
        config = settings.SPOTTER
        return Response(
            {
                "status": "ok",
                "service": "spotter-eld-trip-planner",
                "version": "1.0.0",
                "providers": {
                    "routing": "osrm",
                    "geocoding": "nominatim/photon",
                },
                "rules": {
                    "driving_limit_hours": DEFAULT_RULES.max_drive_hours,
                    "on_duty_window_hours": DEFAULT_RULES.max_window_hours,
                    "break_after_driving_hours": DEFAULT_RULES.break_after_drive_hours,
                    "reset_hours": DEFAULT_RULES.reset_off_hours,
                    "cycle": DEFAULT_RULES.cycle_label,
                    "fuel_interval_miles": DEFAULT_RULES.fuel_interval_miles,
                },
                "endpoints": {
                    "osrm": config["OSRM_BASE_URL"],
                    "nominatim": config["NOMINATIM_BASE_URL"],
                    "photon": config["PHOTON_BASE_URL"],
                },
            }
        )


class PlaceSearchView(APIView):
    """Autocomplete for the three location inputs."""

    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        limit = _requested_limit(request.query_params.get("limit"))

        results = get_geocoder().suggest(query, limit) if query else []
        return Response({"query": query, "results": [place.to_dict() for place in results]})


class PlanTripView(APIView):
    """Build the route, the stop plan and every daily ELD log sheet."""

    def post(self, request):
        serializer = TripPlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        plan = plan_trip(TripPlanRequest.from_validated(serializer.validated_data))
        return Response(plan, status=status.HTTP_200_OK)
