"""HOS rule tests. Pure computation - nothing here touches the network."""

from django.test import SimpleTestCase

from eld.exceptions import ValidationError
from eld.services.hos import (
    DRIVING,
    OFF_DUTY,
    ON_DUTY,
    HosRules,
    HosSimulator,
)
from eld.tests.factories import (
    DEFAULT_START,
    make_route,
    max_rest_gap_minutes,
    shift_groups,
    worked_window,
)

EPSILON_HOURS = 1 / 60.0


class DrivingLimitTests(SimpleTestCase):
    def setUp(self):
        self.rules = HosRules()
        self.simulator = HosSimulator(make_route(2500.0), DEFAULT_START, cycle_used_hours=0.0)
        self.result = self.simulator.simulate()
        self.segments = self.result.segments

    # -- 11-hour driving limit -------------------------------------------
    def test_driving_never_exceeds_eleven_hours_per_shift(self):
        shifts = shift_groups(self.segments)
        self.assertGreaterEqual(len(shifts), 3, "a 2,500 mile run must span several shifts")
        for index, shift in enumerate(shifts):
            driven = sum(s.hours for s in shift if s.status == DRIVING)
            self.assertLessEqual(
                driven,
                self.rules.max_drive_hours + EPSILON_HOURS,
                f"shift {index} drove {driven:.3f} h",
            )

    # -- 14-hour on-duty window ------------------------------------------
    def test_on_duty_window_never_exceeds_fourteen_hours(self):
        for index, shift in enumerate(shift_groups(self.segments)):
            start, end = worked_window(shift)
            elapsed = (end - start).total_seconds() / 3600.0
            self.assertLessEqual(
                elapsed,
                self.rules.max_window_hours + EPSILON_HOURS,
                f"shift {index} spanned {elapsed:.3f} h",
            )

    # -- 30-minute break after 8 hours of driving ------------------------
    def test_thirty_minute_break_after_eight_hours_of_driving(self):
        since_break = 0.0
        worst = 0.0
        for segment in self.segments:
            if segment.status == DRIVING:
                since_break += segment.hours
                worst = max(worst, since_break)
            elif segment.minutes >= self.rules.min_break_minutes:
                since_break = 0.0
        self.assertLessEqual(worst, self.rules.break_after_drive_hours + EPSILON_HOURS)

    # -- 10 consecutive hours off duty -----------------------------------
    def test_there_is_always_a_ten_hour_reset_between_shifts(self):
        self.assertGreaterEqual(
            max_rest_gap_minutes(self.segments),
            self.rules.reset_off_hours * 60 - 0.5,
            "the plan must contain at least one 10-hour reset",
        )
        shifts = shift_groups(self.segments)
        for index in range(len(shifts) - 1):
            tail = worked_window(shifts[index])[1]
            head = worked_window(shifts[index + 1])[0]
            gap = (head - tail).total_seconds() / 3600.0
            self.assertGreaterEqual(gap, self.rules.reset_off_hours - EPSILON_HOURS)

    # -- fuel interval -----------------------------------------------------
    def test_fuel_stops_never_exceed_one_thousand_miles(self):
        accumulated = 0.0
        gaps = []
        for segment in self.segments:
            accumulated += segment.miles
            if segment.kind == "fuel":
                gaps.append(accumulated)
                accumulated = 0.0
        gaps.append(accumulated)
        for gap in gaps:
            self.assertLessEqual(gap, self.rules.fuel_interval_miles + 0.5)
        self.assertEqual(self.result.counters.get("fuel_stops"), len(gaps) - 1)

    # -- structural sanity --------------------------------------------------
    def test_segments_are_contiguous_and_ordered(self):
        for previous, following in zip(self.segments, self.segments[1:]):
            self.assertLessEqual(previous.start, following.start)
            self.assertEqual(previous.end, following.start)

    def test_grid_starts_and_ends_cleanly(self):
        first = self.segments[0]
        last = self.segments[-1]
        self.assertEqual((first.start.hour, first.start.minute), (0, 0))
        self.assertEqual(first.status, OFF_DUTY)
        self.assertEqual(last.status, OFF_DUTY)
        # The sheet must close on a clean midnight, even mid-rest.
        self.assertEqual((last.end.hour, last.end.minute, last.end.second), (0, 0, 0))

    def test_total_miles_matches_the_route(self):
        driven = sum(segment.miles for segment in self.segments)
        self.assertAlmostEqual(driven, self.result.total_miles, places=1)
        self.assertAlmostEqual(driven, 2500.0, delta=1.0)

    def test_pickup_and_dropoff_take_one_hour_each(self):
        pickup = [s for s in self.segments if s.kind == "pickup"]
        dropoff = [s for s in self.segments if s.kind == "dropoff"]
        self.assertEqual(len(pickup), 1)
        self.assertEqual(len(dropoff), 1)
        self.assertAlmostEqual(pickup[0].hours, 1.0, places=6)
        self.assertAlmostEqual(dropoff[0].hours, 1.0, places=6)


class CycleLimitTests(SimpleTestCase):
    def test_seventy_hour_cycle_triggers_a_thirty_four_hour_restart(self):
        result = HosSimulator(
            make_route(2500.0), DEFAULT_START, cycle_used_hours=68.0
        ).simulate()
        restarts = [s for s in result.segments if s.kind == "restart"]
        self.assertGreaterEqual(len(restarts), 1)
        self.assertAlmostEqual(restarts[0].hours, 34.0, places=6)
        self.assertEqual(result.counters.get("restarts"), 1)

    def test_cycle_hours_never_exceed_the_70_hour_limit(self):
        """On-duty time accumulates, but a restart always lands before hour 70."""
        result = HosSimulator(
            make_route(2500.0), DEFAULT_START, cycle_used_hours=68.0
        ).simulate()
        accumulated = 68.0
        for segment in result.segments:
            if segment.kind == "restart":
                accumulated = 0.0
                continue
            if segment.status in (DRIVING, ON_DUTY):
                accumulated += segment.hours
                self.assertLessEqual(
                    accumulated,
                    70.0 + EPSILON_HOURS,
                    f"cycle hit {accumulated:.3f} h at {segment.start}",
                )

    def test_cycle_used_is_validated(self):
        with self.assertRaises(ValidationError):
            HosSimulator(make_route(100.0), DEFAULT_START, cycle_used_hours=71.0)
        with self.assertRaises(ValidationError):
            HosSimulator(make_route(100.0), DEFAULT_START, cycle_used_hours=-1.0)


class ShortTripTests(SimpleTestCase):
    def test_short_trip_needs_no_reset_and_no_fuel(self):
        result = HosSimulator(make_route(400.0), DEFAULT_START).simulate()
        self.assertEqual(result.counters.get("fuel_stops", 0), 0)
        self.assertEqual(result.counters.get("rests", 0), 0)
        self.assertEqual(result.counters.get("restarts", 0), 0)
        driven = sum(s.hours for s in result.segments if s.status == DRIVING)
        self.assertAlmostEqual(driven, 400.0 / 55.0, places=3)

    def test_fuel_stop_also_satisfies_the_break_rule(self):
        result = HosSimulator(make_route(1200.0), DEFAULT_START).simulate()
        self.assertEqual(result.counters.get("fuel_stops", 0), 1)
        since_break = 0.0
        worst = 0.0
        for segment in result.segments:
            if segment.status == DRIVING:
                since_break += segment.hours
                worst = max(worst, since_break)
            elif segment.minutes >= 30:
                since_break = 0.0
        self.assertLessEqual(worst, 8.0 + EPSILON_HOURS)

    def test_custom_rules_are_honoured(self):
        """The engine is data-driven, so alternate rule sets flow straight through."""
        rules = HosRules(max_drive_hours=8.0, fuel_interval_miles=500.0)
        result = HosSimulator(make_route(1200.0), DEFAULT_START, rules=rules).simulate()
        self.assertGreaterEqual(result.counters.get("fuel_stops", 0), 2)
        for shift in shift_groups(result.segments):
            driven = sum(s.hours for s in shift if s.status == DRIVING)
            self.assertLessEqual(driven, 8.0 + EPSILON_HOURS)

