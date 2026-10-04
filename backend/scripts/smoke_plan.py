"""Live end-to-end smoke test for the planner (talks to the real OSM services).

Usage::

    python scripts/smoke_plan.py "Green Bay, WI" "Chicago, IL" "Nashville, TN" 0
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from eld.services.planner import TripPlanRequest, plan_trip  # noqa: E402


def main() -> int:
    argv = sys.argv[1:]
    origin = argv[0] if argv else "Green Bay, WI"
    pickup = argv[1] if len(argv) > 1 else "Chicago, IL"
    dropoff = argv[2] if len(argv) > 2 else "Nashville, TN"
    cycle = float(argv[3]) if len(argv) > 3 else 0.0

    plan = plan_trip(
        TripPlanRequest(
            current_location=origin,
            pickup_location=pickup,
            dropoff_location=dropoff,
            cycle_used_hours=cycle,
            departure_time=datetime(2026, 10, 1, 6, 30),
            start_odometer=142_500,
        )
    )

    summary = plan["summary"]
    print("=== SUMMARY ===")
    for key in (
        "total_miles",
        "driving_hours",
        "wall_clock_hours",
        "trip_days",
        "fuel_stops",
        "breaks",
        "rests",
        "restarts",
        "departure",
        "arrival",
        "cycle_hours_after_trip",
        "cycle_hours_remaining",
    ):
        print(f"  {key:26} {summary[key]}")

    print("\n=== LEGS ===")
    for leg in plan["route"]["legs"]:
        print(f"  {leg['from']:>22} -> {leg['to']:<22} {leg['distance_miles']:>8} mi")
    print(f"  geometry points: {len(plan['route']['geometry'])}")

    print("\n=== STOPS ===")
    for stop in plan["stops"]:
        print(
            f"  {stop['arrive_time']:<12} {stop['title']:<22} {stop['location']:<28} "
            f"{stop['duration_min']:>6} min  @ {stop['miles_from_start']:>7} mi"
        )

    print("\n=== LOG SHEETS ===")
    for day in plan["logs"]:
        header = day["header"]
        print(f"\n  Day {day['day_index']} - {header['day_label']}  ({day['miles_driving']} mi)")
        totals = day["totals"]
        for status in ("off_duty", "sleeper_berth", "driving", "on_duty_not_driving"):
            print(f"    line {totals[status]['line']} {totals[status]['label']:<24} {totals[status]['hhmm']}")
        print(f"    total {day['total_hours_hhmm']} h  |  {len(day['remarks'])} remarks")
        for remark in day["remarks"]:
            flag = "*" if remark["continued"] else " "
            print(f"      {flag} {remark['time']} L{remark['line']} {remark['note']:<42} {remark['location']}")
        recap = day["recap"]
        print(
            f"    RECAP today {recap['hours_on_duty_today_hhmm']} + prev7 "
            f"{recap['hours_previous_seven_days_hhmm']} = {recap['total_hours_on_duty_hhmm']} "
            f"| avail tomorrow {recap['hours_available_tomorrow_hhmm']}"
        )

    out = BACKEND_DIR / "smoke-plan.json"
    out.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
