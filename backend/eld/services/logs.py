"""Turns the HOS segment stream into one FMCSA-style daily log sheet per day.

Each sheet carries everything the paper/graph-grid form needs:

* a 24-hour grid split into 15-minute increments across four duty-status rows,
* the duty-status line (with brackets for on-duty periods where the truck
  never moved), a numbered remark flag at every status change,
* per-line totals, total driving miles, and the 70-hour/8-day recap.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date as date_cls
from datetime import datetime, time, timedelta
from typing import Any

from eld.services.hos import (
    DEFAULT_RULES,
    DRIVING,
    LINE_FOR_STATUS,
    OFF_DUTY,
    ON_DUTY,
    SLEEPER,
    STATUS_LABELS,
    Segment,
)

logger = logging.getLogger(__name__)

MINUTES_PER_DAY = 24 * 60

# Kinds that exist only to square off the 24-hour grid and never deserve a flag.
_SILENT_KINDS = {"prior_off", "post_off"}


def minutes_to_hhmm(total_minutes: float) -> str:
    """``615`` -> ``"10:15"`` (used for the per-line totals box)."""
    total = int(round(total_minutes))
    return f"{total // 60}:{total % 60:02d}"


def hours_to_hhmm(hours: float) -> str:
    return minutes_to_hhmm(hours * 60)


@dataclass
class LogEntry:
    """A duty-status block clipped to a single calendar day."""

    status: str
    line: int
    start_min: float
    end_min: float
    kind: str
    note: str
    location: str
    city: str
    state: str
    lat: float
    lng: float
    miles: float
    stationary: bool

    @property
    def duration_min(self) -> float:
        return self.end_min - self.start_min

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "status_label": STATUS_LABELS[self.status],
            "line": self.line,
            "start_min": round(self.start_min, 2),
            "end_min": round(self.end_min, 2),
            "start_time": _min_to_clock(self.start_min),
            "end_time": _min_to_clock(self.end_min),
            "duration_min": round(self.duration_min, 2),
            "kind": self.kind,
            "note": self.note,
            "location": self.location,
            "city": self.city,
            "state": self.state,
            "lat": round(self.lat, 6),
            "lng": round(self.lng, 6),
            "miles": round(self.miles, 1),
            "stationary": self.stationary,
        }


@dataclass
class Remark:
    """One flagged event in the remarks column."""

    index: int
    at_min: float
    status: str
    line: int
    location: str
    city: str
    state: str
    note: str
    kind: str
    continued: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "at_min": round(self.at_min, 2),
            "time": _min_to_clock(self.at_min),
            "status": self.status,
            "status_label": STATUS_LABELS[self.status],
            "line": self.line,
            "location": self.location,
            "city": self.city,
            "state": self.state,
            "note": self.note,
            "kind": self.kind,
            "continued": self.continued,
        }


@dataclass
class DayLog:
    date: date_cls
    day_index: int
    entries: list[LogEntry] = field(default_factory=list)
    remarks: list[Remark] = field(default_factory=list)
    totals_minutes: dict[str, float] = field(default_factory=dict)
    miles_driving: float = 0.0
    mileage_entries: list[dict[str, Any]] = field(default_factory=list)
    recap: dict[str, Any] = field(default_factory=dict)
    header: dict[str, Any] = field(default_factory=dict)

    @property
    def totals_hours(self) -> dict[str, float]:
        return {status: minutes / 60.0 for status, minutes in self.totals_minutes.items()}

    @property
    def on_duty_hours(self) -> float:
        return (self.totals_minutes.get(DRIVING, 0.0) + self.totals_minutes.get(ON_DUTY, 0.0)) / 60.0

    @property
    def total_hours(self) -> float:
        return sum(self.totals_minutes.values()) / 60.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date.isoformat(),
            "day_index": self.day_index,
            "header": self.header,
            "entries": [e.to_dict() for e in self.entries],
            "remarks": [r.to_dict() for r in self.remarks],
            "totals": {
                status: {
                    "minutes": round(self.totals_minutes.get(status, 0.0), 2),
                    "hours": round(self.totals_minutes.get(status, 0.0) / 60.0, 2),
                    "hhmm": minutes_to_hhmm(self.totals_minutes.get(status, 0.0)),
                    "label": STATUS_LABELS[status],
                    "line": LINE_FOR_STATUS[status],
                }
                for status in (OFF_DUTY, SLEEPER, DRIVING, ON_DUTY)
            },
            "total_hours": round(self.total_hours, 2),
            "total_hours_hhmm": minutes_to_hhmm(sum(self.totals_minutes.values())),
            "miles_driving": round(self.miles_driving, 1),
            "miles_truck": round(self.miles_driving, 1),
            "mileage_entries": self.mileage_entries,
            "recap": self.recap,
        }


def _min_to_clock(minutes: float) -> str:
    total = int(round(minutes)) % MINUTES_PER_DAY
    return f"{total // 60:02d}:{total % 60:02d}"


DEFAULT_HEADER = {
    "driver_name": "J. Driver",
    "driver_number": "SCH-4471",
    "co_driver": "N/A",
    "home_terminal": "Green Bay, WI",
    # 49 CFR 395.8(d)(7) requires the motor carrier's main office address on the
    # form, and (f)(8) requires the time standard of the home terminal.
    "main_office_address": "1200 Velp Ave, Green Bay, WI 54303",
    # (d)(6) the 24-hour period starting time. 395.8(g) draws the specimen grid
    # midnight to midnight, and so do we.
    "period_start_time": "midnight",
    "carrier": "Spotter Freight Systems",
    "tractor_number": "T-1042",
    "trailer_number": "TR-5580",
    "shipper": "Don's Paper Company",
    "commodity": "Paper products",
    "load_id": "LD-88231",
}


class LogBookBuilder:
    """Slices the HOS segment stream into per-day FMCSA log sheets."""

    def __init__(
        self,
        segments: list[Segment],
        *,
        cycle_used_hours: float = 0.0,
        header: dict[str, Any] | None = None,
        start_odometer: float = 0.0,
    ) -> None:
        self.segments = sorted(segments, key=lambda s: s.start)
        self.cycle_used_hours = float(cycle_used_hours)
        self.start_odometer = float(start_odometer or 0.0)
        self.header = {**DEFAULT_HEADER, **(header or {})}

        # Cumulative TRIP miles after each segment (driving segments add miles).
        self._cumulative: list[float] = []
        running = 0.0
        for segment in self.segments:
            running += segment.miles
            self._cumulative.append(running)
        self.total_miles = running

    # -- public ------------------------------------------------------------
    def build(self) -> list[DayLog]:
        if not self.segments:
            return []
        first_day = self.segments[0].start.date()
        last_moment = self.segments[-1].end - timedelta(seconds=1)
        last_day = max(first_day, last_moment.date())

        days: list[DayLog] = []
        cursor = first_day
        index = 1
        while cursor <= last_day:
            days.append(self._build_day(cursor, index))
            cursor += timedelta(days=1)
            index += 1

        self._apply_recap(days)
        return days

    # -- internals ---------------------------------------------------------
    def _cumulative_at(self, moment: datetime) -> float:
        """Trip miles accumulated up to ``moment``."""
        running = 0.0
        for segment, cumulative in zip(self.segments, self._cumulative):
            if segment.end <= moment:
                running = cumulative
            elif segment.start >= moment:
                break
            else:
                span = max(segment.minutes * 60.0, 1e-6)
                share = (moment - segment.start).total_seconds() / span
                running += segment.miles * max(0.0, min(1.0, share))
        return running

    def _build_day(self, day: date_cls, day_index: int) -> DayLog:
        day_start = datetime.combine(day, time.min)
        day_end = day_start + timedelta(days=1)

        entries: list[LogEntry] = []
        for segment in self.segments:
            if segment.end <= day_start or segment.start >= day_end:
                continue
            start = max(segment.start, day_start)
            end = min(segment.end, day_end)
            if end <= start:
                continue
            entries.append(
                LogEntry(
                    status=segment.status,
                    line=LINE_FOR_STATUS[segment.status],
                    start_min=(start - day_start).total_seconds() / 60.0,
                    end_min=(end - day_start).total_seconds() / 60.0,
                    kind=segment.kind,
                    note=segment.note,
                    location=segment.place_label,
                    city=segment.place_city,
                    state=segment.place_state,
                    lat=segment.lat,
                    lng=segment.lng,
                    miles=segment.miles,
                    stationary=segment.stationary,
                )
            )

        totals = {status: 0.0 for status in (OFF_DUTY, SLEEPER, DRIVING, ON_DUTY)}
        for entry in entries:
            totals[entry.status] += entry.duration_min

        miles_driving, mileage_entries = self._mileage(day_start, day_end)
        return DayLog(
            date=day,
            day_index=day_index,
            entries=entries,
            remarks=self._remarks(entries),
            totals_minutes=totals,
            miles_driving=miles_driving,
            mileage_entries=mileage_entries,
            header={
                **self.header,
                "date": day.isoformat(),
                "day_index": day_index,
                "day_label": day.strftime("%a, %b %d, %Y"),
            },
        )

    def _remarks(self, entries: list[LogEntry]) -> list[Remark]:
        """A numbered flag at every duty-status change (FMCSA 395.8 remarks)."""
        remarks: list[Remark] = []
        previous_status: str | None = None
        for position, entry in enumerate(entries):
            if position == 0:
                continued = entry.start_min <= 0.01
                emit = entry.kind not in _SILENT_KINDS
            else:
                continued = False
                emit = entry.status != previous_status
            if emit:
                remarks.append(
                    Remark(
                        index=len(remarks) + 1,
                        at_min=entry.start_min,
                        status=entry.status,
                        line=entry.line,
                        location=entry.location or entry.city,
                        city=entry.city,
                        state=entry.state,
                        note=entry.note,
                        kind=entry.kind,
                        continued=continued,
                    )
                )
            previous_status = entry.status
        return remarks

    def _mileage(
        self, day_start: datetime, day_end: datetime
    ) -> tuple[float, list[dict[str, Any]]]:
        """Total miles driven today plus the odometer readings a driver must note."""
        miles = 0.0
        for segment in self.segments:
            if segment.status != DRIVING or segment.miles <= 0:
                continue
            overlap_start = max(segment.start, day_start)
            overlap_end = min(segment.end, day_end)
            if overlap_end <= overlap_start:
                continue
            span = max(segment.minutes * 60.0, 1e-6)
            share = (overlap_end - overlap_start).total_seconds() / span
            miles += segment.miles * max(0.0, min(1.0, share))

        readings: list[dict[str, Any]] = []

        def add_reading(moment: datetime, note: str, location: str) -> None:
            trip = self._cumulative_at(moment)
            readings.append(
                {
                    "time": moment.strftime("%H:%M"),
                    "note": note,
                    "location": location,
                    "odometer": int(round(self.start_odometer + trip)),
                    "trip_miles": int(round(trip)),
                }
            )

        day_segments = [s for s in self.segments if s.end > day_start and s.start < day_end]
        if day_segments:
            add_reading(
                max(day_segments[0].start, day_start),
                "Begin day",
                day_segments[0].place_label,
            )
            for segment in day_segments:
                if segment.kind == "fuel":
                    add_reading(segment.start, "Fuel stop", segment.place_label)
            tail = day_segments[-1]
            add_reading(
                min(tail.end, day_end - timedelta(minutes=1)),
                "End day",
                tail.place_label,
            )

        deduped: list[dict[str, Any]] = []
        for reading in readings:
            if deduped and deduped[-1]["note"] == reading["note"] and (
                deduped[-1]["odometer"] == reading["odometer"]
            ):
                continue
            deduped.append(reading)

        return round(miles, 1), deduped

    def _apply_recap(self, days: list[DayLog]) -> None:
        """70-hour / 8-day recap - the box at the bottom right of the paper form."""
        limit = DEFAULT_RULES.cycle_limit_hours
        # ``history`` holds prior days.  Index 0 aggregates everything already
        # burned before this trip, which is all a scalar input can tell us.
        history: list[float] = [max(0.0, self.cycle_used_hours)]
        for day in days:
            previous_seven = sum(history[-7:])
            today = day.on_duty_hours
            total = previous_seven + today
            available = max(0.0, limit - total)
            day.recap = {
                "cycle": f"{limit:.0f}-hour / {DEFAULT_RULES.cycle_days}-day",
                "cycle_limit_hours": limit,
                "hours_on_duty_today": round(today, 2),
                "hours_on_duty_today_hhmm": hours_to_hhmm(today),
                "hours_previous_seven_days": round(previous_seven, 2),
                "hours_previous_seven_days_hhmm": hours_to_hhmm(previous_seven),
                "total_hours_on_duty": round(total, 2),
                "total_hours_on_duty_hhmm": hours_to_hhmm(total),
                "hours_available_tomorrow": round(available, 2),
                "hours_available_tomorrow_hhmm": hours_to_hhmm(available),
            }
            history.append(today)
