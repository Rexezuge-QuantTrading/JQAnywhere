"""Dynamic JoinQuant globals."""

from __future__ import annotations

from jqanywhere.runtime.state import get_session


class _Proxy:
    def __init__(self, attr: str):
        object.__setattr__(self, "_attr", attr)

    def _target(self):
        return getattr(get_session(), object.__getattribute__(self, "_attr"))

    def __getattr__(self, name):
        return getattr(self._target(), name)

    def __setattr__(self, name, value):
        setattr(self._target(), name, value)

    def __repr__(self):
        return repr(self._target())


g = _Proxy("g")
context = _Proxy("context")
log = _Proxy("log")
