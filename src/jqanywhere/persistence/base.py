"""State persistence interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class StateStore(ABC):
    @abstractmethod
    def load(self, strategy_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def save(self, strategy_id: str, state: dict[str, Any]) -> None:
        raise NotImplementedError
