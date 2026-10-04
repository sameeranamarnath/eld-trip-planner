"""Request validation for the trip-planner API."""

from rest_framework import serializers

from eld.services.hos import DEFAULT_RULES

# Read from the HOS rules instead of being repeated as a literal, so the
# request validator cannot drift from the limit the simulator enforces.
MAX_CYCLE_HOURS = DEFAULT_RULES.cycle_limit_hours


class LogHeaderSerializer(serializers.Serializer):
    """Optional paper-form header fields; the UI shows them on every log sheet."""

    driver_name = serializers.CharField(max_length=80, required=False)
    driver_number = serializers.CharField(max_length=40, required=False)
    co_driver = serializers.CharField(max_length=40, required=False)
    home_terminal = serializers.CharField(max_length=80, required=False)
    main_office_address = serializers.CharField(max_length=160, required=False)
    carrier = serializers.CharField(max_length=80, required=False)
    tractor_number = serializers.CharField(max_length=40, required=False)
    trailer_number = serializers.CharField(max_length=40, required=False)
    shipper = serializers.CharField(max_length=80, required=False)
    commodity = serializers.CharField(max_length=80, required=False)
    load_id = serializers.CharField(max_length=40, required=False)


class TripPlanRequestSerializer(serializers.Serializer):
    current_location = serializers.CharField(max_length=200)
    pickup_location = serializers.CharField(max_length=200)
    dropoff_location = serializers.CharField(max_length=200)
    cycle_used_hours = serializers.FloatField(
        min_value=0.0, max_value=MAX_CYCLE_HOURS, required=False, default=0.0
    )
    departure_time = serializers.DateTimeField(
        required=False,
        allow_null=True,
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "iso-8601"],
    )
    start_odometer = serializers.FloatField(min_value=0.0, required=False, default=0.0)
    header = LogHeaderSerializer(required=False)

    def validate_current_location(self, value: str) -> str:
        return self._clean_location(value, "Current location")

    def validate_pickup_location(self, value: str) -> str:
        return self._clean_location(value, "Pickup location")

    def validate_dropoff_location(self, value: str) -> str:
        return self._clean_location(value, "Dropoff location")

    @staticmethod
    def _clean_location(value: str, field_label: str) -> str:
        cleaned = " ".join((value or "").split())
        if len(cleaned) < 2:
            raise serializers.ValidationError(f"{field_label} must be at least 2 characters.")
        return cleaned
