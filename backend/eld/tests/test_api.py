"""API surface tests. Every external call is stubbed, so these run offline."""

from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIClient

VALID_PAYLOAD = {
    "current_location": "Green Bay, WI",
    "pickup_location": "Chicago, IL",
    "dropoff_location": "Nashville, TN",
    "cycle_used_hours": 4.5,
    "departure_time": "2026-10-01T06:30",
    "start_odometer": 142_500,
    "header": {"driver_name": "J. Driver", "carrier": "Spotter Freight Systems"},
}


class HealthTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    def test_health_reports_rules_and_providers(self):
        response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["rules"]["driving_limit_hours"], 11.0)
        self.assertEqual(body["rules"]["break_after_driving_hours"], 8.0)
        self.assertEqual(body["rules"]["cycle"], "70 hours / 8 days")
        self.assertEqual(body["rules"]["fuel_interval_miles"], 1000.0)
        self.assertIn("osrm", body["endpoints"])

    def test_root_lists_the_endpoints(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("plan", response.json()["endpoints"])


class ValidationTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    def _post(self, **overrides):
        payload = {**VALID_PAYLOAD, **overrides}
        return self.client.post("/api/v1/plan/", payload, format="json")

    def test_missing_location_is_rejected(self):
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "dropoff_location"}
        response = self.client.post("/api/v1/plan/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "ValidationError")
        self.assertIn("dropoff_location", response.json()["error"]["message"])

    def test_blank_location_is_rejected(self):
        response = self._post(pickup_location="   ")
        self.assertEqual(response.status_code, 400)

    def test_cycle_used_above_seventy_hours_is_rejected(self):
        response = self._post(cycle_used_hours=80)
        self.assertEqual(response.status_code, 400)

    def test_negative_cycle_used_is_rejected(self):
        response = self._post(cycle_used_hours=-2)
        self.assertEqual(response.status_code, 400)

    def test_places_endpoint_handles_a_too_short_query_without_network(self):
        response = self.client.get("/api/v1/places/?q=a")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])


class PlanEndpointTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    @patch("eld.views.plan_trip")
    def test_successful_plan_is_returned_untouched(self, mocked_plan):
        stub = {
            "input": {},
            "places": {"current": {}, "pickup": {}, "dropoff": {}},
            "route": {"distance_miles": 100.0, "legs": [], "geometry": [], "bounds": {}},
            "stops": [],
            "segments": [],
            "logs": [],
            "summary": {"total_miles": 100.0},
        }
        mocked_plan.return_value = stub
        response = self.client.post("/api/v1/plan/", VALID_PAYLOAD, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), stub)

        request = mocked_plan.call_args.args[0]
        self.assertEqual(request.current_location, "Green Bay, WI")
        self.assertEqual(request.cycle_used_hours, 4.5)
        self.assertEqual(request.start_odometer, 142_500)
        self.assertEqual(request.departure_time.isoformat(), "2026-10-01T06:30:00")
        self.assertEqual(request.header["driver_name"], "J. Driver")

    @patch("eld.views.plan_trip")
    def test_locations_are_whitespace_normalised(self, mocked_plan):
        mocked_plan.return_value = {"summary": {}}
        self.client.post(
            "/api/v1/plan/",
            {**VALID_PAYLOAD, "pickup_location": "  Chicago,   IL  "},
            format="json",
        )
        self.assertEqual(mocked_plan.call_args.args[0].pickup_location, "Chicago, IL")

    @patch("eld.views.plan_trip")
    def test_domain_errors_render_as_a_json_envelope(self, mocked_plan):
        from eld.exceptions import PlaceNotFoundError

        mocked_plan.side_effect = PlaceNotFoundError("Could not find 'Nowhere, XX'.")
        response = self.client.post("/api/v1/plan/", VALID_PAYLOAD, format="json")
        self.assertEqual(response.status_code, 422)
        body = response.json()["error"]
        self.assertEqual(body["code"], "PlaceNotFoundError")
        self.assertIn("Nowhere", body["message"])

    @patch("eld.views.plan_trip")
    def test_upstream_failures_render_as_503(self, mocked_plan):
        from eld.exceptions import UpstreamServiceError

        mocked_plan.side_effect = UpstreamServiceError("provider down")
        response = self.client.post("/api/v1/plan/", VALID_PAYLOAD, format="json")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "UpstreamServiceError")

    @patch("eld.views.plan_trip")
    def test_departure_time_is_optional(self, mocked_plan):
        mocked_plan.return_value = {"summary": {}}
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "departure_time"}
        response = self.client.post("/api/v1/plan/", payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(mocked_plan.call_args.args[0].departure_time)
