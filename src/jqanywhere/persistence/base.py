"""State persistence interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RunClaim:
    claimed: bool
    state: dict[str, Any]


class StateStore(ABC):
    @abstractmethod
    def load(self, strategy_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def save(self, strategy_id: str, state: dict[str, Any]) -> None:
        raise NotImplementedError

    def claim_run(self, strategy_id: str, state: dict[str, Any], run_key: str) -> RunClaim:
        metadata = dict(state.get("metadata", {}))
        if metadata.get("last_run_key") == run_key or not _can_claim_active_key(metadata.get("active_run_key"), run_key):
            return RunClaim(False, state)
        metadata["revision"] = int(metadata.get("revision", 0)) + 1
        metadata["active_run_key"] = run_key
        metadata["last_status"] = "running"
        next_state = dict(state)
        next_state["metadata"] = metadata
        self.save(strategy_id, next_state)
        return RunClaim(True, next_state)


def _can_claim_active_key(active_run_key: str | None, run_key: str) -> bool:
    return active_run_key is None or active_run_key < run_key
