"""In-memory state store."""

from __future__ import annotations

import copy
from typing import Any

from jqanywhere.persistence.base import RunClaim, StateStore, _can_claim_active_key


class MemoryStateStore(StateStore):
    def __init__(self):
        self._items: dict[str, dict[str, Any]] = {}

    def load(self, strategy_id: str) -> dict[str, Any]:
        return copy.deepcopy(self._items.get(strategy_id, {}))

    def save(self, strategy_id: str, state: dict[str, Any]) -> None:
        self._items[strategy_id] = copy.deepcopy(state)

    def claim_run(self, strategy_id: str, state: dict[str, Any], run_key: str) -> RunClaim:
        current = self.load(strategy_id)
        metadata = dict(current.get("metadata", {}))
        if metadata.get("last_run_key") == run_key or not _can_claim_active_key(metadata.get("active_run_key"), run_key):
            return RunClaim(False, current)
        metadata["revision"] = int(metadata.get("revision", 0)) + 1
        metadata["active_run_key"] = run_key
        metadata["last_status"] = "running"
        next_state = copy.deepcopy(state)
        next_state["metadata"] = metadata
        self.save(strategy_id, next_state)
        return RunClaim(True, copy.deepcopy(next_state))
