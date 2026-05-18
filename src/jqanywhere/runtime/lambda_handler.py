"""AWS Lambda entrypoint."""

from __future__ import annotations

from datetime import datetime

from jqanywhere.config import load_config
from jqanywhere.runtime.factory import build_engine


def run(event=None, context=None):
    config = load_config()
    return build_engine(config).run(now=_event_time(event))


def _event_time(event) -> datetime | None:
    if not isinstance(event, dict) or not event.get("time"):
        return None
    return datetime.fromisoformat(event["time"].replace("Z", "+00:00"))
