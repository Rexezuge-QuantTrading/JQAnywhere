"""In-process schedule registry for JoinQuant run_daily callbacks."""

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


@dataclass
class Scheduler:
    jobs: list[ScheduledJob] = field(default_factory=list)

    def run_daily(self, func: Callable, time: str, reference_security: str = "") -> None:
        _parse_time(time)
        self.jobs.append(ScheduledJob(func=func, time=time, reference_security=reference_security))

    def due_jobs(self, now: datetime) -> list[ScheduledJob]:
        return [job for job in self.jobs if _parse_time(job.time) == (now.hour, now.minute)]


def _parse_time(value: str) -> tuple[int, int]:
    match = _TIME_PATTERN.match(value)
    if not match:
        raise NotImplementedError("JQAnywhere v0.4 run_daily only supports HH:MM schedule times")
    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    if hour > 23 or minute > 59:
        raise ValueError("run_daily time must be a valid HH:MM time")
    return hour, minute
