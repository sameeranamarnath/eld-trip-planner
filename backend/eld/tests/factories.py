"""Offline builders for the HOS tests - no network, no fixtures."""

from __future__ import annotations

from datetime import datetime

from eld.services.hos import DRIVING, OFF_DUTY, ON_DUTY, SLEEPER
from eld.services.routing import PathLeg, RoutePath

DEFAULT_START = datetime(2026, 3, 2, 6, 0)


def make_route(total_miles: float = 1200.0, speed_mph: float = 55.0) -> RoutePath:
    """A straight synthetic route: current -> pickup -> drop-off.

    ``position_at`` only needs monotonic cumulative mileage, so the geometry is
    a placeholder line with enough points to interpolate cleanly.
    """
    pickup_at = total_miles * 0.5
    sample_count = 240
    points = [
        (
            total_miles * index / (sample_count - 1),
            40.0 + index * 0.01,
            -100.0 + index * 0.02,
        )
        for index in range(sample_count)
    ]

    specs = [
        ("Origin, WI", "Pickup, IL", 0.0, pickup_at),
        ("Pickup, IL", "Dropoff, TN", pickup_at, total_miles),
    ]
    legs = [
        PathLeg(
            label_from=label_from,
            label_to=label_to,
            start_miles=start,
            distance_miles=end - start,
            duration_hours=(end - start) / speed_mph,
        )
        for label_from, label_to, start, end in specs
    ]

    return RoutePath(
        points=points,
        legs=legs,
        total_miles=total_miles,
        total_hours=total_miles / speed_mph,
    )


def shift_groups(segments: list) -> list[list]:
    """Split the segment stream into shifts at every >=10 h non-driving block."""
    groups: list[list] = []
    current: list = []
    rest_run = 0.0

    for segment in segments:
        if segment.status in (OFF_DUTY, SLEEPER):
            rest_run += segment.minutes
        else:
            if rest_run >= 600 and current:
                groups.append(current)
                current = []
            rest_run = 0.0
        current.append(segment)

    if current:
        groups.append(current)
    return groups


def worked_window(group: list) -> tuple:
    """Return ``(first_on_duty_start, last_on_duty_end)`` for a shift group.

    ``shift_groups`` keeps the carry-over block that opens the sheet and the
    10-hour reset that closes the shift inside the group; the 14-hour *window*
    runs from the first on-duty moment to the last, and any 30-minute break in
    between legitimately sits inside it.
    """
    worked = [s for s in group if s.status in (DRIVING, ON_DUTY)]
    return worked[0].start, worked[-1].end


def max_rest_gap_minutes(segments: list) -> float:
    """Longest run of consecutive non-driving time anywhere in the trip."""
    best = 0.0
    run = 0.0
    for segment in segments:
        if segment.status in (OFF_DUTY, SLEEPER):
            run += segment.minutes
            best = max(best, run)
        else:
            run = 0.0
    return best
