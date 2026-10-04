from django.urls import path

from eld import views

app_name = "eld"

urlpatterns = [
    path("health/", views.HealthView.as_view(), name="health"),
    path("places/", views.PlaceSearchView.as_view(), name="place-search"),
    path("plan/", views.PlanTripView.as_view(), name="plan-trip"),
]
