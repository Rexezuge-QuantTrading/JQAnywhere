"""AWS Lambda entrypoint."""

from __future__ import annotations

from jqanywhere.config import load_config
from jqanywhere.runtime.factory import build_engine


def run(event=None, context=None):
    config = load_config()
    return build_engine(config).run()
