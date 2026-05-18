"""Console notifier."""

from __future__ import annotations

import sys

from jqanywhere.notifications.base import Notifier


class ConsoleNotifier(Notifier):
    def send(self, subject: str, message: str) -> None:
        if message:
            print(f"{subject}\n{message}", file=sys.stderr)
