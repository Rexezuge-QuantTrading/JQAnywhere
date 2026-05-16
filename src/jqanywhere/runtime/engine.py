"""JQAnywhere runtime engine."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jqanywhere.broker.base import Broker
from jqanywhere.data.base import MarketDataProvider
from jqanywhere.jqcompat.logging import BufferedLogger
from jqanywhere.jqcompat.types import Context, Portfolio
from jqanywhere.notifications.base import Notifier
from jqanywhere.persistence.base import StateStore
from jqanywhere.runtime.loader import load_strategy
from jqanywhere.runtime.scheduler import Scheduler
from jqanywhere.runtime.state import G, RuntimeSession, bind_session, reset_session


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
    ):
        self.strategy_id = strategy_id
        self.strategy_path = Path(strategy_path)
        self.data = data
        self.broker = broker
        self.state_store = state_store
        self.notifier = notifier
        self.initial_cash = initial_cash

    def run(self, now: datetime | None = None) -> dict:
        now = now or datetime.now()
        log = BufferedLogger()
        g = G()
        g.load_dict(self.state_store.load(self.strategy_id))
        context = Context(portfolio=Portfolio(self.initial_cash, self.initial_cash), current_dt=now)
        scheduler = Scheduler()
        session = RuntimeSession(self.strategy_id, context, g, log, scheduler, self.data, self.broker)
        token = bind_session(session)
        try:
            module = load_strategy(self.strategy_path)
            if not hasattr(module, "initialize"):
                raise AttributeError("Strategy must define initialize(context)")
            module.initialize(context)
            for job in scheduler.due_jobs(now):
                job.func(context)
            state = g.to_dict()
            self.state_store.save(self.strategy_id, state)
            logs = log.flush_text()
            self.notifier.send(f"JQAnywhere {self.strategy_id}", logs)
            return {
                "status": "completed",
                "strategy_id": self.strategy_id,
                "logs": logs,
                "state": state,
                "portfolio_value": context.portfolio.total_value,
            }
        finally:
            reset_session(token)
