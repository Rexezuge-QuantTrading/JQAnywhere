"""In-process schedule registry for JoinQuant run_daily callbacks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScheduledJob:
    func: Callable
    time: str
    reference_security: str = ""


@dataclass
class Scheduler:
    jobs: list[ScheduledJob] = field(default_factory=list)

    def run_daily(self, func: Callable, time: str, reference_security: str = "") -> None:
        self.jobs.append(ScheduledJob(func=func, time=time, reference_security=reference_security))

    def due_jobs(self, _now=None) -> list[ScheduledJob]:
        return list(self.jobs)
