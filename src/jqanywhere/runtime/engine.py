"""JQAnywhere runtime engine."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from jqanywhere.broker.base import Broker
from jqanywhere.data.base import MarketDataProvider
from jqanywhere.jqcompat.logging import BufferedLogger
from jqanywhere.jqcompat.types import Context, Portfolio, Position
from jqanywhere.notifications.base import Notifier
from jqanywhere.persistence.base import StateStore
from jqanywhere.runtime.loader import load_strategy
from jqanywhere.runtime.scheduler import Scheduler
from jqanywhere.runtime.state import G, RuntimeSession, bind_session, reset_session

_STATE_VERSION = 1
_STATE_VERSION_KEY = "__jqanywhere_state_version__"


class RuntimeEngine:
    def __init__(
        self,
        strategy_id: str,
        strategy_path: str | Path,
        data: MarketDataProvider,
        broker: Broker,
        state_store: StateStore,
        notifier: Notifier,
        initial_cash: float = 100_000.0,
        timezone: str = "Asia/Shanghai",
    ):
        self.strategy_id = strategy_id
        self.strategy_path = Path(strategy_path)
        self.data = data
        self.broker = broker
        self.state_store = state_store
        self.notifier = notifier
        self.initial_cash = initial_cash
        self.timezone = timezone

    def run(self, now: datetime | None = None) -> dict:
        now = self._normalize_now(now)
        log = BufferedLogger()
        g = G()
        persisted_g, portfolio, has_persisted_g = _decode_runtime_state(self.state_store.load(self.strategy_id), self.initial_cash)
        context = Context(portfolio=portfolio, current_dt=now, previous_date=self._previous_date(now))
        scheduler = Scheduler()
        session = RuntimeSession(self.strategy_id, context, g, log, scheduler, self.data, self.broker)
        token = bind_session(session)
        try:
            module = load_strategy(self.strategy_path)
            if not hasattr(module, "initialize"):
                raise AttributeError("Strategy must define initialize(context)")
            module.initialize(context)
            if has_persisted_g:
                g.load_dict(persisted_g)
            for job in scheduler.due_jobs(now):
                job.func(context)
            state = g.to_dict()
            self.state_store.save(self.strategy_id, _encode_runtime_state(state, context.portfolio))
            logs = log.flush_text()
            self.notifier.send(f"JQAnywhere {self.strategy_id}", logs)
            return {
                "status": "completed",
                "strategy_id": self.strategy_id,
                "logs": logs,
                "state": state,
                "portfolio": _portfolio_to_dict(context.portfolio),
                "portfolio_value": context.portfolio.total_value,
            }
        finally:
            reset_session(token)

    def _normalize_now(self, now: datetime | None) -> datetime:
        timezone = ZoneInfo(self.timezone)
        if now is None:
            return datetime.now(timezone)
        if now.tzinfo is None:
            return now.replace(tzinfo=timezone)
        return now.astimezone(timezone)

    def _previous_date(self, now: datetime):
        try:
            trade_days = self.data.get_trade_days(end_date=now.date() - timedelta(days=1), count=1)
        except NotImplementedError:
            return None
        return trade_days[-1] if trade_days else None


def _decode_runtime_state(raw_state: dict[str, Any], initial_cash: float) -> tuple[dict[str, Any], Portfolio, bool]:
    if raw_state.get(_STATE_VERSION_KEY) == _STATE_VERSION:
        return dict(raw_state.get("g", {})), _portfolio_from_dict(raw_state.get("portfolio"), initial_cash), True
    return dict(raw_state), Portfolio(initial_cash, initial_cash), bool(raw_state)


def _encode_runtime_state(g_state: dict[str, Any], portfolio: Portfolio) -> dict[str, Any]:
    return {_STATE_VERSION_KEY: _STATE_VERSION, "g": g_state, "portfolio": _portfolio_to_dict(portfolio)}


def _portfolio_to_dict(portfolio: Portfolio) -> dict[str, Any]:
    return {
        "starting_cash": portfolio.starting_cash,
        "available_cash": portfolio.available_cash,
        "positions": {
            security: {
                "security": position.security,
                "total_amount": position.total_amount,
                "closeable_amount": position.closeable_amount,
                "price": position.price,
                "avg_cost": position.avg_cost,
                "value": position.value,
            }
            for security, position in portfolio.positions.items()
        },
    }


def _portfolio_from_dict(data: dict[str, Any] | None, initial_cash: float) -> Portfolio:
    if not data:
        return Portfolio(initial_cash, initial_cash)
    positions = {}
    for security, position_data in data.get("positions", {}).items():
        positions[str(security)] = Position(
            security=str(position_data.get("security", security)),
            total_amount=int(position_data.get("total_amount", 0)),
            closeable_amount=int(position_data.get("closeable_amount", 0)),
            price=float(position_data.get("price", 0.0)),
            avg_cost=float(position_data.get("avg_cost", 0.0)),
            value=float(position_data.get("value", 0.0)),
        )
    return Portfolio(
        starting_cash=float(data.get("starting_cash", initial_cash)),
        available_cash=float(data.get("available_cash", initial_cash)),
        positions=positions,
    )
