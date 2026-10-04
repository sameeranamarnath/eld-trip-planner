"""Domain exceptions plus a DRF exception handler that renders them as JSON."""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class SpotterError(Exception):
    """Base class for expected, user-facing failures."""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(SpotterError):
    status_code = status.HTTP_400_BAD_REQUEST


class PlaceNotFoundError(SpotterError):
    """A user supplied a location we could not resolve to coordinates."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class UpstreamServiceError(SpotterError):
    """A third-party routing/geocoding provider failed or timed out."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE


class RoutingError(SpotterError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


def api_exception_handler(exc, context):
    """Return ``{"error": {"code", "message", "details"}}`` for every failure."""
    if isinstance(exc, SpotterError):
        return Response(
            {
                "error": {
                    "code": exc.__class__.__name__,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
            status=exc.status_code,
        )

    response = drf_exception_handler(exc, context)
    if response is not None:
        response.data = {
            "error": {
                "code": "ValidationError",
                "message": _flatten(response.data),
                "details": response.data if isinstance(response.data, dict) else {},
            }
        }
        return response

    return None


def _flatten(payload) -> str:
    if isinstance(payload, dict):
        parts = []
        for key, value in payload.items():
            parts.append(f"{key}: {_flatten(value)}")
        return "; ".join(parts)
    if isinstance(payload, (list, tuple)):
        return ", ".join(_flatten(item) for item in payload)
    return str(payload)
