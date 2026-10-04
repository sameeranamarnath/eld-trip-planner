from django.http import JsonResponse
from django.urls import include, path


def root(_request):
    return JsonResponse(
        {
            "service": "Spotter ELD Trip Planner API",
            "version": "1.0.0",
            "endpoints": {
                "health": "/api/v1/health/",
                "places": "/api/v1/places/?q=Chicago,IL",
                "plan": "POST /api/v1/plan/",
            },
        }
    )


urlpatterns = [
    path("", root),
    path("api/v1/", include("eld.urls")),
]
