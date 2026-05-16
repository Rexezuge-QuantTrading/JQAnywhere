"""In-memory state store."""

from __future__ import annotations

from typing import Any

from jqanywhere.persistence.base import StateStore


class MemoryStateStore(StateStore):
    def __init__(self):
        self._items: dict[str, dict[str, Any]] = {}

    def load(self, strategy_id: str) -> dict[str, Any]:
        return dict(self._items.get(strategy_id, {}))

    def save(self, strategy_id: str, state: dict[str, Any]) -> None:
        self._items[strategy_id] = dict(state)
