"""In-process schedule registry for JoinQuant scheduled callbacks."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

_TIME_PATTERN = re.compile(r"^(?P<hour>\d{1,2}):(?P<minute>\d{2})$")


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
    if _parse_time(job.time) != (now.hour, now.minute):
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
    match = _TIME_PATTERN.match(value)
    if not match:
        raise NotImplementedError("JQAnywhere v0.5 scheduled jobs only support HH:MM schedule times")
    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    if hour > 23 or minute > 59:
        raise ValueError("run_daily time must be a valid HH:MM time")
    return hour, minute
