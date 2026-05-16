"""Runtime-local state and global accessors."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from jqanywhere.broker.base import Broker
from jqanywhere.data.base import MarketDataProvider
from jqanywhere.jqcompat.logging import BufferedLogger
from jqanywhere.jqcompat.types import Context
from jqanywhere.runtime.scheduler import Scheduler


class G:
    """Mutable strategy namespace compatible with JoinQuant's g."""

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    def load_dict(self, data: dict[str, Any]) -> None:
        self.__dict__.clear()
        self.__dict__.update(data)


@dataclass
class RuntimeSession:
    strategy_id: str
    context: Context
    g: G
    log: BufferedLogger
    scheduler: Scheduler
    data: MarketDataProvider
    broker: Broker
    options: dict[str, Any] = field(default_factory=dict)
    benchmark: str | None = None
    slippage: Any = None
    order_cost: Any = None


_session: ContextVar[RuntimeSession | None] = ContextVar("jqanywhere_session", default=None)


def bind_session(session: RuntimeSession):
    return _session.set(session)


def reset_session(token) -> None:
    _session.reset(token)


def get_session() -> RuntimeSession:
    session = _session.get()
    if session is None:
        raise RuntimeError("No active JQAnywhere runtime session")
    return session
