"""Contract check for a running stack.

Posts the sample request through the Vite proxy into Django and asserts that
every field the React UI reads is present, plus the HOS invariants that hold
for any plan.

Usage::

    python scripts/verify_contract.py [base_url]
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SAMPLE = HERE / "sample_request.json"
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5173/api/v1"

problems: list[str] = []
checks = 0

STATUSES = {"off_duty", "sleeper_berth", "driving", "on_duty_not_driving"}


def check(condition: bool, message: str) -> None:
    global checks
    checks += 1
    if not condition:
        problems.append(message)


def has_keys(mapping: dict, keys: list[str], where: str) -> None:
    for key in keys:
        check(key in mapping, f"{where}: missing key '{key}'")


def verify_places(plan: dict) -> None:
    for name in ("current", "pickup", "dropoff"):
        place = plan["places"][name]
        has_keys(place, ["label", "short_label", "city", "state", "lat", "lng"], f"places.{name}")
        check(-90 <= place["lat"] <= 90 and -180 <= place["lng"] <= 180, f"places.{name} coords")
        check(bool(place["short_label"]), f"places.{name} has no short_label")


def verify_route(plan: dict) -> None:
    route = plan["route"]
    has_keys(route,
             ["distance_miles", "duration_hours", "geometry", "bounds", "legs", "provider"],
             "route")
    has_keys(route["bounds"], ["min_lat", "max_lat", "min_lng", "max_lng"], "route.bounds")
    check(len(route["geometry"]) > 10, "route.geometry is too small")
    check(all(len(point) == 2 for point in route["geometry"]), "route.geometry points malformed")
    check(len(route["legs"]) == 2, "expected exactly two legs (current->pickup->dropoff)")
    for leg in route["legs"]:
        has_keys(leg, ["index", "from", "to", "distance_miles", "duration_hours"], "route.legs[]")


def verify_stops(plan: dict) -> None:
    stops = plan["stops"]
    check(len(stops) >= 3, "expected at least pickup, dropoff and one rest stop")
    for stop in stops:
        has_keys(stop,
                 ["type", "title", "status", "status_label", "note", "location", "city", "state",
                  "lat", "lng", "arrive", "depart", "arrive_time", "depart_time", "duration_min",
                  "miles_from_start", "date"],
                 "stops[]")
    kinds = [stop["type"] for stop in stops]
    check(kinds.count("pickup") == 1, "expected exactly one pickup stop")
    check(kinds.count("dropoff") == 1, "expected exactly one dropoff stop")


def verify_logs(plan: dict) -> None:
    logs = plan["logs"]
    check(len(logs) >= 1, "no log sheets produced")
    for day in logs:
        where = f"logs[{day.get('day_index')}]"
        has_keys(day, ["date", "day_index", "header", "entries", "remarks", "totals",
                       "total_hours_hhmm", "miles_driving", "mileage_entries", "recap"], where)
        has_keys(day["header"],
                 ["driver_name", "carrier", "home_terminal", "tractor_number", "trailer_number",
                  "shipper", "commodity", "load_id", "date", "day_index", "day_label",
                  "driver_number", "co_driver"],
                 f"{where}.header")
        has_keys(day["recap"],
                 ["hours_on_duty_today_hhmm", "hours_previous_seven_days_hhmm",
                  "total_hours_on_duty_hhmm", "hours_available_tomorrow_hhmm",
                  "cycle_limit_hours", "cycle"],
                 f"{where}.recap")

        total_minutes = 0.0
        driving_minutes = 0.0
        for entry in day["entries"]:
            has_keys(entry,
                     ["status", "line", "start_min", "end_min", "duration_min", "kind", "note",
                      "location", "city", "lat", "lng", "stationary"],
                     f"{where}.entries[]")
            check(entry["status"] in STATUSES, f"{where}: unknown status {entry['status']}")
            check(0 <= entry["start_min"] <= 1440, f"{where}: start_min out of range")
            check(entry["end_min"] >= entry["start_min"], f"{where}: end before start")
            check(abs(entry["duration_min"] - (entry["end_min"] - entry["start_min"])) < 0.05,
                  f"{where}: duration_min mismatch")
            total_minutes += entry["duration_min"]
            if entry["status"] == "driving":
                driving_minutes += entry["duration_min"]

        check(abs(total_minutes - 1440) < 1.0,
              f"{where}: grid totals {total_minutes:.1f} min, expected 1440")
        check(driving_minutes <= 11 * 60 + 0.5,
              f"{where}: {driving_minutes / 60:.2f} h driving exceeds the 11-hour limit")
        check(day["miles_driving"] >= 0, f"{where}: negative miles")

        for status in STATUSES:
            has_keys(day["totals"][status], ["minutes", "hours", "hhmm", "label", "line"],
                     f"{where}.totals.{status}")
        check(abs(day["totals"]["driving"]["minutes"] - driving_minutes) < 0.5,
              f"{where}: driving total disagrees with entries")

        for remark in day["remarks"]:
            has_keys(remark,
                     ["index", "at_min", "time", "status", "line", "location", "city", "note",
                      "kind", "continued"],
                     f"{where}.remarks[]")
        check(len(day["remarks"]) >= 1, f"{where}: no remarks produced")

        for reading in day["mileage_entries"]:
            has_keys(reading, ["time", "note", "location", "odometer", "trip_miles"],
                     f"{where}.mileage_entries[]")


def verify_summary(plan: dict) -> None:
    summary = plan["summary"]
    has_keys(summary,
             ["total_miles", "driving_hours", "trip_days", "log_sheets", "wall_clock_hours",
              "wall_clock_days", "departure", "arrival", "fuel_stops", "breaks", "rests",
              "restarts", "cycle_used_hours", "cycle_hours_after_trip",
              "cycle_hours_remaining", "rules"],
             "summary")
    has_keys(summary["rules"],
             ["max_drive_hours", "max_window_hours", "break_after_drive_hours", "reset_off_hours",
              "cycle", "fuel_interval_miles", "pickup_minutes", "dropoff_minutes"],
             "summary.rules")
    check(summary["log_sheets"] == len(plan["logs"]), "summary.log_sheets disagrees with logs[]")
    check(summary["arrival"] > summary["departure"], "arrival is not after departure")

    previous = 0.0
    for stop in plan["stops"]:
        if stop["type"] != "fuel":
            continue
        gap = stop["miles_from_start"] - previous
        check(gap <= 1000.5, f"fuel gap {gap:.1f} mi exceeds the 1,000 mi interval")
        previous = stop["miles_from_start"]
    tail = summary["total_miles"] - previous
    check(tail <= 1000.5, f"final fuel gap {tail:.1f} mi exceeds the 1,000 mi interval")


def main() -> int:
    payload = json.loads(SAMPLE.read_text(encoding="utf-8"))
    request = urllib.request.Request(
        f"{BASE}/plan/",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        plan = json.loads(response.read().decode())

    has_keys(plan, ["input", "places", "route", "stops", "segments", "logs", "summary"], "plan")
    verify_places(plan)
    verify_route(plan)
    verify_stops(plan)
    verify_logs(plan)
    verify_summary(plan)

    summary = plan["summary"]
    print(f"checks run   : {checks}")
    print(f"log sheets   : {len(plan['logs'])}")
    print(f"stops        : {len(plan['stops'])}")
    print(f"miles        : {summary['total_miles']}")
    print(f"departure    : {summary['departure']}")
    print(f"arrival      : {summary['arrival']}")
    print(f"fuel/breaks/resets: {summary['fuel_stops']}/{summary['breaks']}/{summary['rests']}")
    for day in plan["logs"]:
        print(
            f"  day {day['day_index']} {day['date']}  drive {day['totals']['driving']['hhmm']}"
            f"  onduty {day['totals']['on_duty_not_driving']['hhmm']}"
            f"  off {day['totals']['off_duty']['hhmm']}"
            f"  sb {day['totals']['sleeper_berth']['hhmm']}"
            f"  total {day['total_hours_hhmm']}  miles {day['miles_driving']:>6}"
            f"  remarks {len(day['remarks'])}"
        )

    if problems:
        print(f"\nFAILED ({len(problems)} problems):")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
