"""In-process schedule registry for JoinQuant scheduled callbacks."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

_TIME_PATTERN = re.compile(r"^(?P<hour>\d{1,2}):(?P<minute>\d{2})$")
_TIME_ALIASES = {
    "before_open": "09:00",
    "open": "09:30",
    "close": "15:00",
    "after_close": "15:30",
}
_EVERY_BAR = "every_bar"


@dataclass(frozen=True)
class ScheduledJob:
    func: Callable
    time: str
    reference_security: str = ""
    frequency: str = "daily"
    weekday: int | None = None
    monthday: int | None = None


@dataclass
class Scheduler:
    jobs: list[ScheduledJob] = field(default_factory=list)

    def run_daily(self, func: Callable, time: str, reference_security: str = "") -> None:
        _parse_time(time)
        self.jobs.append(ScheduledJob(func=func, time=time, reference_security=reference_security))

    def run_weekly(self, func: Callable, weekday: int, time: str, reference_security: str = "") -> None:
        if not isinstance(weekday, int) or weekday < 1 or weekday > 5:
            raise ValueError("run_weekly weekday must be an integer from 1 to 5")
        _parse_time(time)
        self.jobs.append(ScheduledJob(func=func, time=time, reference_security=reference_security, frequency="weekly", weekday=weekday))

    def run_monthly(self, func: Callable, monthday: int, time: str, reference_security: str = "") -> None:
        if not isinstance(monthday, int) or monthday == 0 or monthday < -31 or monthday > 31:
            raise ValueError("run_monthly monthday must be an integer from -31 to -1 or 1 to 31")
        _parse_time(time)
        self.jobs.append(ScheduledJob(func=func, time=time, reference_security=reference_security, frequency="monthly", monthday=monthday))

    def due_jobs(self, now: datetime, trade_days=None) -> list[ScheduledJob]:
        return [job for job in self.jobs if _is_due(job, now, trade_days)]


def _is_due(job: ScheduledJob, now: datetime, trade_days=None) -> bool:
    if job.time == _EVERY_BAR:
        if not _is_every_bar_minute(now):
            return False
    elif _parse_time(job.time) != (now.hour, now.minute):
        return False
    if trade_days and now.date() not in set(trade_days):
        return False
    if job.frequency == "daily":
        return True
    if job.frequency == "weekly":
        return _trade_day_index(now, trade_days, "week") == job.weekday
    if job.frequency == "monthly":
        return _trade_day_index(now, trade_days, "month", job.monthday) == job.monthday
    return False


def _trade_day_index(now: datetime, trade_days, period: str, requested: int | None = None) -> int | None:
    today = now.date()
    days = sorted(day for day in (trade_days or []) if _same_period(day, today, period))
    if today not in days:
        return None
    if requested is not None and requested < 0:
        return days.index(today) - len(days)
    forward = days.index(today) + 1
    if forward <= len(days):
        return forward
    return None


def _same_period(day, today, period: str) -> bool:
    if period == "week":
        return day.isocalendar()[:2] == today.isocalendar()[:2]
    return day.year == today.year and day.month == today.month


def _parse_time(value: str) -> tuple[int, int]:
    if value == _EVERY_BAR:
        return (-1, -1)
    if value in _TIME_ALIASES:
        value = _TIME_ALIASES[value]
    match = _TIME_PATTERN.match(value)
    if not match:
        raise NotImplementedError(
            "JQAnywhere v0.9.0 scheduled jobs support HH:MM, every_bar, and before_open/open/close/after_close aliases"
        )
    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    if hour > 23 or minute > 59:
        raise ValueError("run_daily time must be a valid HH:MM time")
    return hour, minute


def _is_every_bar_minute(now: datetime) -> bool:
    # Minimal v0.9.0 support: every_bar is driven by external per-minute invocations.
    # JQAnywhere does not synthesize a 240-bar intraday loop inside one run.
    minute_of_day = now.hour * 60 + now.minute
    return (9 * 60 + 30 <= minute_of_day <= 11 * 60 + 29) or (13 * 60 <= minute_of_day <= 14 * 60 + 59)
