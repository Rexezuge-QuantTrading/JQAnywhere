"""JQAnywhere runtime engine."""

from __future__ import annotations

import time
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
        started_at = time.monotonic()
        log = BufferedLogger()
        g = G()
        context = None
        token = None
        due_job_names = []
        try:
            persisted_g, portfolio, has_persisted_g, metadata, order_history = _decode_runtime_state(
                self.state_store.load(self.strategy_id), self.initial_cash
            )
            context = Context(portfolio=portfolio, current_dt=now, previous_date=self._previous_date(now), order_history=order_history)
            self.broker.sync_portfolio(context)
            scheduler = Scheduler()
            session = RuntimeSession(self.strategy_id, context, g, log, scheduler, self.data, self.broker)
            token = bind_session(session)
            module = load_strategy(self.strategy_path)
            if not hasattr(module, "initialize"):
                raise AttributeError("Strategy must define initialize(context)")
            module.initialize(context)
            if has_persisted_g:
                g.load_dict(persisted_g)
            trade_days = self._trade_days_for_schedule()
            due_jobs = scheduler.due_jobs(now, trade_days=trade_days)
            run_key = _run_key(now)
            before_hook = _strategy_hook(module, "before_trading_start")
            after_hook = _strategy_hook(module, "after_trading_end")
            due_job_names = (
                [*_hook_names(before_hook), *[_job_name(job.func) for job in due_jobs], *_hook_names(after_hook)] if due_jobs else []
            )
            if due_jobs and metadata.get("last_run_key") == run_key:
                log.info(f"Skipping duplicate scheduled run for {run_key}")
                logs = log.flush_text()
                result = _runtime_result(
                    "skipped",
                    self.strategy_id,
                    now,
                    g.to_dict(),
                    context.portfolio,
                    logs,
                    due_job_names,
                    started_at,
                    metadata=metadata,
                    reason="duplicate_scheduled_run",
                )
                self._notify_result(result, logs)
                return result

            if due_job_names:
                claim_state = _encode_runtime_state(g.to_dict(), context.portfolio, metadata, context.order_history)
                claim = self.state_store.claim_run(self.strategy_id, claim_state, run_key)
                if not claim.claimed:
                    claimed_g, claimed_portfolio, _, claimed_metadata, claimed_orders = _decode_runtime_state(
                        claim.state, self.initial_cash
                    )
                    log.info(f"Skipping locked or duplicate scheduled run for {run_key}")
                    logs = log.flush_text()
                    result = _runtime_result(
                        "skipped",
                        self.strategy_id,
                        now,
                        claimed_g,
                        claimed_portfolio,
                        logs,
                        due_job_names,
                        started_at,
                        metadata=claimed_metadata,
                        orders=claimed_orders,
                        reason="scheduled_run_claim_failed",
                    )
                    self._notify_result(result, logs)
                    return result
                metadata = dict(claim.state.get("metadata", metadata))

            if due_jobs and before_hook is not None:
                before_hook(context)
            for job in due_jobs:
                job.func(context)
            if due_jobs and after_hook is not None:
                after_hook(context)
            state = g.to_dict()
            metadata = _next_metadata(metadata, now, run_key, due_job_names, "completed")
            self.state_store.save(self.strategy_id, _encode_runtime_state(state, context.portfolio, metadata, context.order_history))
            logs = log.flush_text()
            result = _runtime_result(
                "completed",
                self.strategy_id,
                now,
                state,
                context.portfolio,
                logs,
                due_job_names,
                started_at,
                metadata=metadata,
                orders=context.order_history,
            )
            self._notify_result(result, logs)
            return result
        except Exception as exc:
            logs = log.flush_text()
            portfolio = context.portfolio if context is not None else None
            order_history = context.order_history if context is not None else []
            metadata = _failure_metadata(locals().get("metadata", {}), now, exc)
            if context is not None:
                self.state_store.save(self.strategy_id, _encode_runtime_state(g.to_dict(), context.portfolio, metadata, order_history))
            result = _runtime_result(
                "failed",
                self.strategy_id,
                now,
                g.to_dict(),
                portfolio,
                logs,
                due_job_names,
                started_at,
                metadata=metadata,
                orders=order_history,
                error={"type": type(exc).__name__, "message": str(exc)},
            )
            self._notify_result(result, logs)
            return result
        finally:
            if token is not None:
                reset_session(token)

    def _notify_result(self, result: dict[str, Any], logs: str) -> None:
        subject = f"JQAnywhere {result['strategy_id']} {result['status']}"
        message = _notification_message(result, logs)
        try:
            self.notifier.send(subject, message)
        except Exception as exc:  # pragma: no cover - notifier failures depend on external services.
            result["notification_error"] = {"type": type(exc).__name__, "message": str(exc)}

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

    def _trade_days_for_schedule(self):
        try:
            return self.data.get_all_trade_days()
        except NotImplementedError:
            return []


def _decode_runtime_state(
    raw_state: dict[str, Any], initial_cash: float
) -> tuple[dict[str, Any], Portfolio, bool, dict[str, Any], list[dict[str, Any]]]:
    if raw_state.get(_STATE_VERSION_KEY) == _STATE_VERSION:
        return (
            dict(raw_state.get("g", {})),
            _portfolio_from_dict(raw_state.get("portfolio"), initial_cash),
            True,
            dict(raw_state.get("metadata", {})),
            list(raw_state.get("orders", [])),
        )
    return dict(raw_state), Portfolio(initial_cash, initial_cash), bool(raw_state), {}, []


def _encode_runtime_state(
    g_state: dict[str, Any], portfolio: Portfolio, metadata: dict[str, Any] | None = None, orders: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    return {
        _STATE_VERSION_KEY: _STATE_VERSION,
        "g": g_state,
        "portfolio": _portfolio_to_dict(portfolio),
        "metadata": metadata or {},
        "orders": orders or [],
    }


def _runtime_result(
    status: str,
    strategy_id: str,
    now: datetime,
    state: dict[str, Any],
    portfolio: Portfolio | None,
    logs: str,
    due_jobs: list[str],
    started_at: float,
    *,
    metadata: dict[str, Any] | None = None,
    reason: str | None = None,
    error: dict[str, str] | None = None,
    orders: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    result = {
        "status": status,
        "strategy_id": strategy_id,
        "event_time": now.isoformat(),
        "due_jobs": due_jobs,
        "duration_seconds": round(time.monotonic() - started_at, 6),
        "logs": logs,
        "state": state,
        "portfolio": _portfolio_to_dict(portfolio) if portfolio is not None else None,
        "portfolio_value": portfolio.total_value if portfolio is not None else None,
        "metadata": metadata or {},
        "orders": orders or [],
    }
    if reason is not None:
        result["reason"] = reason
    if error is not None:
        result["error"] = error
    return result


def _notification_message(result: dict[str, Any], logs: str) -> str:
    lines = [
        f"status: {result['status']}",
        f"strategy_id: {result['strategy_id']}",
        f"event_time: {result['event_time']}",
        f"due_jobs: {', '.join(result['due_jobs']) if result['due_jobs'] else '-'}",
        f"portfolio_value: {result['portfolio_value']}",
    ]
    if "reason" in result:
        lines.append(f"reason: {result['reason']}")
    if "error" in result:
        lines.append(f"error: {result['error']['type']}: {result['error']['message']}")
    if logs:
        lines.extend(["", logs])
    return "\n".join(lines)


def _next_metadata(metadata: dict[str, Any], now: datetime, run_key: str, due_jobs: list[str], status: str) -> dict[str, Any]:
    next_metadata = dict(metadata)
    next_metadata["revision"] = int(next_metadata.get("revision", 0)) + 1
    next_metadata["updated_at"] = now.isoformat()
    next_metadata["last_status"] = status
    next_metadata["last_due_jobs"] = due_jobs
    next_metadata.pop("active_run_key", None)
    if due_jobs:
        next_metadata["last_run_key"] = run_key
        next_metadata["last_run_at"] = now.isoformat()
    return next_metadata


def _failure_metadata(metadata: dict[str, Any], now: datetime, exc: Exception) -> dict[str, Any]:
    next_metadata = dict(metadata)
    next_metadata["revision"] = int(next_metadata.get("revision", 0)) + 1
    next_metadata["updated_at"] = now.isoformat()
    next_metadata["last_status"] = "failed"
    next_metadata["last_failed_at"] = now.isoformat()
    next_metadata["last_error"] = {"type": type(exc).__name__, "message": str(exc)}
    next_metadata.pop("active_run_key", None)
    return next_metadata


def _strategy_hook(module, name: str):
    hook = getattr(module, name, None)
    if hook is None or getattr(hook, "__module__", None) == "jqanywhere.jqcompat.api":
        return None
    return hook


def _hook_names(hook) -> list[str]:
    return [_job_name(hook)] if hook is not None else []


def _run_key(now: datetime) -> str:
    return now.replace(second=0, microsecond=0).isoformat()


def _job_name(func) -> str:
    return getattr(func, "__name__", repr(func))


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
