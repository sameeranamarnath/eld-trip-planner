"""Daily-log-sheet tests: grid totals, remarks, mileage and the 70-hour recap."""

from django.test import SimpleTestCase

from eld.services.hos import DRIVING, HosSimulator
from eld.services.logs import LogBookBuilder, hours_to_hhmm, minutes_to_hhmm
from eld.tests.factories import DEFAULT_START, make_route


class FormatterTests(SimpleTestCase):
    def test_minutes_to_hhmm(self):
        self.assertEqual(minutes_to_hhmm(0), "0:00")
        self.assertEqual(minutes_to_hhmm(615), "10:15")
        self.assertEqual(minutes_to_hhmm(1440), "24:00")

    def test_hours_to_hhmm(self):
        self.assertEqual(hours_to_hhmm(10.5), "10:30")
        self.assertEqual(hours_to_hhmm(0), "0:00")


class MultiDayLogTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        result = HosSimulator(make_route(2111.0), DEFAULT_START).simulate()
        cls.days = LogBookBuilder(
            result.segments, cycle_used_hours=0.0, start_odometer=142_500
        ).build()

    def test_one_sheet_per_calendar_day_of_the_trip(self):
        self.assertGreaterEqual(len(self.days), 3)
        dates = [day.date for day in self.days]
        self.assertEqual(dates, sorted(dates))
        self.assertEqual(len(dates), len(set(dates)))

    def test_every_grid_totals_exactly_twenty_four_hours(self):
        for day in self.days:
            self.assertAlmostEqual(sum(day.totals_minutes.values()), 1440.0, places=3)
            self.assertAlmostEqual(day.total_hours, 24.0, places=3)

    def test_driving_totals_never_exceed_the_daily_limit(self):
        for day in self.days:
            self.assertLessEqual(day.totals_minutes[DRIVING] / 60.0, 11.0 + 1 / 60.0)

    def test_remark_flags_are_sequential_and_start_at_one(self):
        for day in self.days:
            self.assertGreater(len(day.remarks), 0)
            self.assertEqual(
                [remark.index for remark in day.remarks],
                list(range(1, len(day.remarks) + 1)),
            )

    def test_flag_count_matches_duty_status_changes(self):
        silent_kinds = {"prior_off", "post_off"}
        for day in self.days:
            expected = 0
            previous = None
            for position, entry in enumerate(day.entries):
                if position == 0:
                    # A carry-over block only squares the grid; it is not a change.
                    expected += 0 if entry.kind in silent_kinds else 1
                elif entry.status != previous:
                    expected += 1
                previous = entry.status
            self.assertEqual(len(day.remarks), expected, day.date)

    def test_leading_grid_filler_never_raises_a_flag(self):
        checked = False
        for day in self.days:
            if day.entries[0].kind in ("prior_off", "post_off"):
                checked = True
                self.assertGreater(day.remarks[0].at_min, 0.01, day.date)
        self.assertTrue(checked, "expected at least one sheet to open mid-rest")

    def test_each_remark_sits_on_a_real_duty_status_change(self):
        for day in self.days:
            for remark in day.remarks:
                match = [
                    entry
                    for entry in day.entries
                    if abs(entry.start_min - remark.at_min) < 0.01
                ]
                self.assertTrue(match, f"remark {remark.index} has no entry at its time")
                self.assertEqual(match[0].line, remark.line)

    def test_recap_uses_the_seventy_hour_cycle(self):
        history = 0.0
        for day in self.days:
            recap = day.recap
            self.assertAlmostEqual(recap["hours_previous_seven_days"], history, places=2)
            self.assertAlmostEqual(
                recap["total_hours_on_duty"],
                recap["hours_on_duty_today"] + recap["hours_previous_seven_days"],
                places=1,
            )
            self.assertAlmostEqual(
                recap["hours_available_tomorrow"],
                max(0.0, 70.0 - recap["total_hours_on_duty"]),
                places=1,
            )
            history += recap["hours_on_duty_today"]

    def test_recap_carries_the_opening_cycle_balance(self):
        days = LogBookBuilder(
            HosSimulator(make_route(1200.0), DEFAULT_START).simulate().segments,
            cycle_used_hours=23.5,
        ).build()
        self.assertAlmostEqual(days[0].recap["hours_previous_seven_days"], 23.5, places=2)

    def test_mileage_is_split_across_days_without_loss(self):
        total = sum(day.miles_driving for day in self.days)
        self.assertAlmostEqual(total, 2111.0, delta=1.0)

    def test_odometer_readings_are_monotonic(self):
        readings = [r for day in self.days for r in day.mileage_entries]
        odometers = [r["odometer"] for r in readings]
        self.assertEqual(odometers, sorted(odometers))
        self.assertGreater(odometers[-1], odometers[0])

    def test_every_entry_carries_the_header_the_form_needs(self):
        for day in self.days:
            for key in (
                "driver_name",
                "driver_number",
                "co_driver",
                "home_terminal",
                "carrier",
                "tractor_number",
                "trailer_number",
                "shipper",
                "commodity",
                "load_id",
                "day_label",
            ):
                self.assertTrue(day.header.get(key), f"missing header field {key}")

    def test_sheet_carries_the_49_cfr_395_8_d_elements(self):
        """49 CFR 395.8(d) lists what the form must show in addition to the grid.

        Every element a driver hand-writes onto the paper form has to exist in
        the payload the SVG sheet is drawn from, otherwise the drawn form is
        incomplete no matter how good the grid looks.
        """
        for day in self.days:
            payload = day.to_dict()
            header = payload["header"]
            # (d)(1) date, (d)(2) total miles driving today, (d)(3) tractor and
            # trailer number, (d)(4) carrier, (d)(7) main office address,
            # (d)(9) co-driver, (d)(10) total hours, (d)(11) shipping document
            # number / shipper and commodity.
            for key in (
                "date",
                "day_label",
                "carrier",
                "main_office_address",
                "co_driver",
                "tractor_number",
                "trailer_number",
                "shipper",
                "commodity",
                "load_id",
            ):
                self.assertTrue(header.get(key), f"395.8(d) field {key} is empty")
            self.assertGreater(payload["miles_driving"], 0)  # (d)(2)
            self.assertGreater(len(payload["remarks"]), 0)  # (d)(8)
            # (d)(10) total hours, far right edge of the grid.
            self.assertEqual(payload["total_hours_hhmm"], "24:00")

    def test_main_office_address_can_be_overridden(self):
        """(d)(7) is carrier data, so it must come from the request when given."""
        days = LogBookBuilder(
            HosSimulator(make_route(600.0), DEFAULT_START).simulate().segments,
            header={"main_office_address": "500 Dock St, Memphis, TN 38103"},
        ).build()
        self.assertEqual(
            days[0].header["main_office_address"], "500 Dock St, Memphis, TN 38103"
        )
        # The 24-hour period start is fixed at midnight (395.8(g)).
        self.assertEqual(days[0].header["period_start_time"], "midnight")

    def test_sleeper_berth_is_logged_for_overnight_rest(self):
        kinds = {entry.kind for day in self.days for entry in day.entries}
        self.assertIn("reset_sleeper", kinds)
        self.assertIn("reset_off", kinds)

    def test_serialised_shape_matches_the_frontend_contract(self):
        for day in self.days:
            payload = day.to_dict()
            for key in (
                "date",
                "day_index",
                "header",
                "entries",
                "remarks",
                "totals",
                "total_hours_hhmm",
                "miles_driving",
                "mileage_entries",
                "recap",
            ):
                self.assertIn(key, payload)
            for status in ("off_duty", "sleeper_berth", "driving", "on_duty_not_driving"):
                self.assertIn(status, payload["totals"])
                self.assertIn("hhmm", payload["totals"][status])
