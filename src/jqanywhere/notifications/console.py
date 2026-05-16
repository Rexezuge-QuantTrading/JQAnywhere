"""Console notifier."""

from __future__ import annotations

from jqanywhere.notifications.base import Notifier


class ConsoleNotifier(Notifier):
    def send(self, subject: str, message: str) -> None:
        if message:
            print(f"{subject}\n{message}")
