"""Hours-of-Service simulation engine.

Models a solo, property-carrying driver under FMCSA 395.3, with these values as
the defaults:

* 11-hour driving limit / 14-hour on-duty window / 30-minute break after 8 hours
  of accumulated driving / 10 consecutive hours off duty to reset.
* 70 hours in 8 consecutive days with a 34-hour restart.
* Fuel at least once every 1,000 miles.
* 1 hour for pickup and 1 hour for drop-off, 30-minute pre/post-trip inspections.

The engine is pure: give it a :class:`~eld.services.routing.RoutePath` and a
start time, and it returns a chronologically ordered list of duty-status
segments suitable for both the map and the ELD log sheets.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from eld.exceptions import ValidationError
from eld.services.routing import RoutePath

logger = logging.getLogger(__name__)

# --- duty statuses ---------------------------------------------------------
OFF_DUTY = "off_duty"
SLEEPER = "sleeper_berth"
DRIVING = "driving"
ON_DUTY = "on_duty_not_driving"

ALL_STATUSES = (OFF_DUTY, SLEEPER, DRIVING, ON_DUTY)

# FMCSA graph-grid line numbers.
LINE_FOR_STATUS = {OFF_DUTY: 1, SLEEPER: 2, DRIVING: 3, ON_DUTY: 4}
STATUS_LABELS = {
    OFF_DUTY: "Off Duty",
    SLEEPER: "Sleeper Berth",
    DRIVING: "Driving",
    ON_DUTY: "On Duty (Not Driving)",
}

EPSILON = 1e-6


@dataclass(frozen=True)
class HosRules:
    """Every tunable number in the simulation, in one auditable place."""

    max_drive_hours: float = 11.0
    max_window_hours: float = 14.0
    break_after_drive_hours: float = 8.0
    min_break_minutes: int = 30
    reset_off_hours: float = 10.0
    cycle_limit_hours: float = 70.0
    cycle_days: int = 8
    restart_hours: float = 34.0
    fuel_interval_miles: float = 1000.0

    pre_trip_minutes: int = 30
    post_trip_minutes: int = 30
    pickup_minutes: int = 60
    dropoff_minutes: int = 60
    fuel_minutes: int = 30
    break_minutes: int = 30

    # The 10-hour reset is logged the way drivers actually log it: a short
    # off-duty tail following the post-trip inspection, then the sleeper berth.
    reset_off_duty_minutes: int = 60

    @property
    def reset_sleeper_minutes(self) -> int:
        return int(round(self.reset_off_hours * 60)) - self.reset_off_duty_minutes

    @property
    def cycle_label(self) -> str:
        """``"70 hours / 8 days"`` - the cycle rule in the form the UI shows it."""
        return f"{self.cycle_limit_hours:.0f} hours / {self.cycle_days} days"


DEFAULT_RULES = HosRules()


@dataclass
class Segment:
    """A single duty-status block on the log grid."""

    status: str
    start: datetime
    end: datetime
    kind: str
    note: str
    lat: float
    lng: float
    miles: float = 0.0
    stationary: bool = True
    place_label: str = ""
    place_city: str = ""
    place_state: str = ""

    @property
    def minutes(self) -> float:
        return (self.end - self.start).total_seconds() / 60.0

    @property
    def hours(self) -> float:
        return self.minutes / 60.0

    @property
    def line(self) -> int:
        return LINE_FOR_STATUS[self.status]

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "status_label": STATUS_LABELS[self.status],
            "line": self.line,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "kind": self.kind,
            "note": self.note,
            "lat": round(self.lat, 6),
            "lng": round(self.lng, 6),
            "miles": round(self.miles, 1),
            "stationary": self.stationary,
            "location": self.place_label,
            "city": self.place_city,
            "state": self.place_state,
        }


@dataclass
class SimulationResult:
    segments: list[Segment] = field(default_factory=list)
    start_time: datetime | None = None
    end_time: datetime | None = None
    log_end_time: datetime | None = None
    total_miles: float = 0.0
    counters: dict[str, int] = field(default_factory=dict)


class HosSimulator:
    """Walks a route while enforcing every FMCSA clock a property carrier faces."""

    MAX_ITERATIONS = 2000

    def __init__(
        self,
        path: RoutePath,
        start: datetime,
        cycle_used_hours: float = 0.0,
        rules: HosRules | None = None,
    ) -> None:
        self.rules = rules or DEFAULT_RULES
        limit = self.rules.cycle_limit_hours
        if cycle_used_hours < 0 or cycle_used_hours > limit:
            raise ValidationError(
                f"Current cycle used must be between 0 and {limit:.0f} hours.",
                details={"cycle_used_hours": cycle_used_hours},
            )
        self.path = path
        self.t = start
        self.start_time = start
        self.segments: list[Segment] = []

        # Rolling clocks
        self.cum_miles = 0.0
        self.drive_used = 0.0  # hours driven since the last 10-hour reset
        self.break_drive = 0.0  # hours driven since the last >=30 min interruption
        self.window_start: datetime | None = None
        self.cycle_hours = float(cycle_used_hours)
        self.since_fuel = 0.0
        self.odo = 0.0
        self.counters: dict[str, int] = {}

    # -- small helpers ---------------------------------------------------
    def _pos(self) -> tuple[float, float]:
        return self.path.position_at(self.cum_miles)

    def _window_used_hours(self) -> float:
        if self.window_start is None:
            return 0.0
        return (self.t - self.window_start).total_seconds() / 3600.0

    def _add(
        self,
        status: str,
        start: datetime,
        end: datetime,
        kind: str,
        note: str,
        *,
        miles: float = 0.0,
        stationary: bool = True,
        lat: float | None = None,
        lng: float | None = None,
    ) -> None:
        if lat is None or lng is None:
            lat, lng = self._pos()
        self.segments.append(
            Segment(
                status=status,
                start=start,
                end=end,
                kind=kind,
                note=note,
                lat=lat,
                lng=lng,
                miles=miles,
                stationary=stationary,
            )
        )

    def _bump(self, key: str, amount: int = 1) -> None:
        self.counters[key] = self.counters.get(key, 0) + amount

    def _start_window_if_needed(self) -> None:
        if self.window_start is None:
            self.window_start = self.t

    # -- primitive activities --------------------------------------------
    def _on_duty_minutes(self, minutes: int, kind: str, note: str) -> None:
        """On-duty-not-driving block: burns the window and the 70-hour cycle."""
        if minutes <= 0:
            return
        self._start_window_if_needed()
        start = self.t
        end = start + timedelta(minutes=minutes)
        self._add(ON_DUTY, start, end, kind, note)
        self.t = end
        self.cycle_hours += minutes / 60.0
        if minutes >= self.rules.min_break_minutes:
            # 30+ continuous minutes of non-driving satisfies the 8-hour break rule.
            self.break_drive = 0.0

    def _rest_minutes(self, minutes: int, status: str, kind: str, note: str) -> None:
        """Off-duty/sleeper block: pauses the driving clocks, not the cycle clock."""
        if minutes <= 0:
            return
        start = self.t
        end = start + timedelta(minutes=minutes)
        self._add(status, start, end, kind, note)
        self.t = end
        if minutes >= self.rules.min_break_minutes:
            self.break_drive = 0.0
        if minutes / 60.0 >= self.rules.reset_off_hours - EPSILON:
            self.drive_used = 0.0
            self.break_drive = 0.0
            self.window_start = None

    def _drive(self, distance: float, speed_mph: float) -> None:
        """Advance along the route by ``distance`` miles at ``speed_mph``."""
        if distance <= 0:
            return
        speed = speed_mph if speed_mph > 1 else 55.0
        hours = distance / speed
        start = self.t
        end = start + timedelta(hours=hours)
        lat, lng = self._pos()
        self.cum_miles += distance
        self._add(
            DRIVING,
            start,
            end,
            "drive",
            "Driving",
            miles=distance,
            stationary=False,
            lat=lat,
            lng=lng,
        )
        self.t = end
        self.drive_used += hours
        self.break_drive += hours
        self.cycle_hours += hours
        self.since_fuel += distance
        self.odo += distance

    # -- planning decisions ------------------------------------------------
    def _available_miles(self, speed_mph: float) -> float:
        rules = self.rules
        caps = [
            (rules.max_drive_hours - self.drive_used) * speed_mph,
            (rules.max_window_hours - self._window_used_hours()) * speed_mph,
            (rules.break_after_drive_hours - self.break_drive) * speed_mph,
            rules.fuel_interval_miles - self.since_fuel,
            (rules.cycle_limit_hours - self.cycle_hours) * speed_mph,
        ]
        return max(0.0, min(caps))

    def _required_action(self) -> str | None:
        rules = self.rules
        if self.cycle_hours >= rules.cycle_limit_hours - EPSILON:
            return "restart"
        if self.window_start is not None and self._window_used_hours() >= rules.max_window_hours - EPSILON:
            return "reset"
        if self.drive_used >= rules.max_drive_hours - EPSILON:
            return "reset"
        if self.break_drive >= rules.break_after_drive_hours - EPSILON:
            return "break"
        if self.since_fuel >= rules.fuel_interval_miles - EPSILON:
            return "fuel"
        return None

    # -- cycle guard -------------------------------------------------------
    def _ensure_cycle_room(self, minutes: int) -> None:
        """Take a 34-hour restart *before* an on-duty block would breach 70 hours.

        The 11/14-hour clocks are enforced by :meth:`_available_miles`, but an
        on-duty block (pre-trip, loading, unloading, fuelling) is booked as an
        indivisible unit, so it needs its own look-ahead - otherwise the cycle
        could drift past 70 hours by up to an hour before the next driving check
        fires.
        """
        limit = self.rules.cycle_limit_hours
        if self.cycle_hours + minutes / 60.0 >= limit - EPSILON:
            self._perform("restart")

    # -- actions -----------------------------------------------------------
    def _begin_shift(self) -> None:
        """Start a new on-duty period with the mandatory pre-trip inspection."""
        if self.window_start is not None:
            return
        self._ensure_cycle_room(self.rules.pre_trip_minutes)
        self._on_duty_minutes(self.rules.pre_trip_minutes, "pretrip", "Pre-trip inspection")

    def _perform(self, action: str) -> None:
        rules = self.rules
        if action == "restart":
            self._rest_minutes(
                int(round(rules.restart_hours * 60)),
                OFF_DUTY,
                "restart",
                "34-hour restart (70-hour/8-day cycle reset)",
            )
            self.cycle_hours = 0.0
            self.drive_used = 0.0
            self.break_drive = 0.0
            self.window_start = None
            self._bump("restarts")
            return

        if action == "reset":
            self._rest_minutes(
                rules.reset_off_duty_minutes, OFF_DUTY, "reset_off", "Off duty (end of shift)"
            )
            self._rest_minutes(
                rules.reset_sleeper_minutes, SLEEPER, "reset_sleeper", "Sleeper berth (10-hour reset)"
            )
            self.drive_used = 0.0
            self.break_drive = 0.0
            self.window_start = None
            self._bump("rests")
            return

        if action == "break":
            self._rest_minutes(
                rules.break_minutes, OFF_DUTY, "break", "30-minute break"
            )
            self._bump("breaks")
            return

        if action == "fuel":
            self._ensure_cycle_room(rules.fuel_minutes)
            self._on_duty_minutes(rules.fuel_minutes, "fuel", "Fuel stop")
            self.since_fuel = 0.0
            self._bump("fuel_stops")
            return

        raise ValueError(f"Unknown HOS action: {action!r}")  # pragma: no cover

    # -- main loop ---------------------------------------------------------
    def _run_leg(self, leg) -> None:
        remaining = leg.distance_miles
        if remaining <= 0.005:
            return
        speed = leg.speed_mph
        iterations = 0

        while remaining > 0.01:
            iterations += 1
            if iterations > self.MAX_ITERATIONS:  # pragma: no cover - safety valve
                logger.error("HOS simulation stalled on leg %s", leg.label_to)
                break

            self._begin_shift()
            action = self._required_action()
            if action:
                if action == "break":
                    # If a fuel stop is imminent, satisfy both with one stop.
                    fuel_gap = self.rules.fuel_interval_miles - self.since_fuel
                    if fuel_gap <= speed * (self.rules.break_minutes / 60.0):
                        action = "fuel"
                self._perform(action)
                continue

            capacity = self._available_miles(speed)
            if capacity <= 0.01:
                self._perform(self._required_action() or "break")
                continue

            chunk = min(capacity, remaining)
            self._drive(chunk, speed)
            remaining -= chunk

    def _pickup(self) -> None:
        self._begin_shift()
        self._ensure_cycle_room(self.rules.pickup_minutes)
        self._on_duty_minutes(
            self.rules.pickup_minutes, "pickup", "Pickup - loading freight, BOL signed"
        )

    def _dropoff(self) -> None:
        self._begin_shift()
        self._ensure_cycle_room(self.rules.dropoff_minutes + self.rules.post_trip_minutes)
        self._on_duty_minutes(
            self.rules.dropoff_minutes, "dropoff", "Dropoff - unloading freight, POD signed"
        )
        self._on_duty_minutes(self.rules.post_trip_minutes, "posttrip", "Post-trip inspection")

    def simulate(self) -> SimulationResult:
        """Run the trip and return the chronologically ordered duty segments."""
        legs = self.path.legs
        if not legs:
            raise ValidationError("A route with at least one leg is required.")

        self._prepend_prior_off_duty()

        last_index = len(legs) - 1
        for index, leg in enumerate(legs):
            self._run_leg(leg)
            if index == 0:
                self._pickup()
            if index == last_index:
                self._dropoff()

        # The truck is done here - the off-duty tail only exists to square off
        # the last 24-hour log grid.
        trip_end = self.t
        self._append_off_duty_to_midnight()

        return SimulationResult(
            segments=self.segments,
            start_time=self.start_time,
            end_time=trip_end,
            log_end_time=self.t,
            total_miles=round(self.odo, 1),
            counters=dict(self.counters),
        )

    # -- day bookends -------------------------------------------------------
    def _prepend_prior_off_duty(self) -> None:
        """Fill midnight -> shift start so day one of the log grid totals 24 h."""
        midnight = datetime.combine(self.start_time.date(), time.min)
        if self.start_time <= midnight:
            return
        lat, lng = self.path.position_at(0.0)
        self.segments.insert(
            0,
            Segment(
                status=OFF_DUTY,
                start=midnight,
                end=self.start_time,
                kind="prior_off",
                note="Off duty - before shift",
                lat=lat,
                lng=lng,
                stationary=True,
            ),
        )

    def _append_off_duty_to_midnight(self) -> None:
        """Fill the last shift's tail with off duty so the final grid totals 24 h."""
        end_of_day = datetime.combine(self.t.date(), time.min) + timedelta(days=1)
        if end_of_day <= self.t:
            return
        self._add(OFF_DUTY, self.t, end_of_day, "post_off", "Off duty - end of trip")
        self.t = end_of_day
