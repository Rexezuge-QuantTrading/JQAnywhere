from datetime import datetime
from pathlib import Path

from jqanywhere.broker.paper import PaperBroker
from jqanywhere.data.base import EmptyMarketDataProvider, StaticMarketDataProvider
from jqanywhere.jqcompat.types import CurrentData
from jqanywhere.notifications.console import ConsoleNotifier
from jqanywhere.persistence.memory import MemoryStateStore
from jqanywhere.runtime.engine import RuntimeEngine
from jqanywhere.runtime.lambda_handler import _event_time


def test_simple_strategy_runs():
    engine = RuntimeEngine(
        strategy_id="test",
        strategy_path=Path("examples/simple_daily_allocation.py"),
        data=EmptyMarketDataProvider(),
        broker=PaperBroker(),
        state_store=MemoryStateStore(),
        notifier=ConsoleNotifier(),
        initial_cash=100_000,
    )

    result = engine.run(now=datetime(2026, 5, 18, 9, 50))

    assert result["status"] == "completed"
    assert result["portfolio_value"] == 100_000
    assert "order_target_value" in result["logs"]


def test_unsupported_fundamentals_is_explicit():
    from jqanywhere.jqcompat.api import get_fundamentals

    try:
        get_fundamentals(None)
    except NotImplementedError as exc:
        assert "v0.5" in str(exc)
    else:
        raise AssertionError("get_fundamentals should be unsupported")


def test_run_daily_only_runs_matching_time(tmp_path):
    strategy_path = tmp_path / "scheduled_strategy.py"
    strategy_path.write_text(
        "from jqdata import *\n"
        "\n"
        "def initialize(context):\n"
        "    g.ran = False\n"
        "    run_daily(trade, '09:50')\n"
        "\n"
        "def trade(context):\n"
        "    g.ran = True\n",
        encoding="utf-8",
    )
    store = MemoryStateStore()
    engine = RuntimeEngine(
        strategy_id="scheduled",
        strategy_path=strategy_path,
        data=EmptyMarketDataProvider(),
        broker=PaperBroker(),
        state_store=store,
        notifier=ConsoleNotifier(),
        initial_cash=100_000,
    )

    early = engine.run(now=datetime(2026, 5, 18, 9, 49))
    due = engine.run(now=datetime(2026, 5, 18, 9, 50))

    assert early["state"]["ran"] is False
    assert due["state"]["ran"] is True


def test_runtime_persists_g_and_portfolio_across_runs(tmp_path):
    strategy_path = tmp_path / "stateful_strategy.py"
    strategy_path.write_text(
        "from jqdata import *\n"
        "\n"
        "def initialize(context):\n"
        "    g.count = 0\n"
        "    run_daily(trade, '09:50')\n"
        "\n"
        "def trade(context):\n"
        "    g.count += 1\n"
        "    order_value('000001.XSHE', 10)\n",
        encoding="utf-8",
    )
    store = MemoryStateStore()
    engine = RuntimeEngine(
        strategy_id="stateful",
        strategy_path=strategy_path,
        data=EmptyMarketDataProvider(),
        broker=PaperBroker(),
        state_store=store,
        notifier=ConsoleNotifier(),
        initial_cash=100_000,
    )

    first = engine.run(now=datetime(2026, 5, 18, 9, 50))
    second = engine.run(now=datetime(2026, 5, 19, 9, 50))

    assert first["state"]["count"] == 1
    assert second["state"]["count"] == 2
    assert first["portfolio"]["available_cash"] == 99_990
    assert second["portfolio"]["available_cash"] == 99_980
    assert second["portfolio"]["positions"]["000001.XSHE"]["value"] == 20


def test_runtime_skips_duplicate_scheduled_event(tmp_path):
    strategy_path = tmp_path / "duplicate_strategy.py"
    strategy_path.write_text(
        "from jqdata import *\n"
        "\n"
        "def initialize(context):\n"
        "    g.count = 0\n"
        "    run_daily(trade, '09:50')\n"
        "\n"
        "def trade(context):\n"
        "    g.count += 1\n"
        "    order_value('000001.XSHE', 10)\n",
        encoding="utf-8",
    )
    store = MemoryStateStore()
    engine = RuntimeEngine(
        strategy_id="duplicate",
        strategy_path=strategy_path,
        data=EmptyMarketDataProvider(),
        broker=PaperBroker(),
        state_store=store,
        notifier=ConsoleNotifier(),
        initial_cash=100_000,
    )

    first = engine.run(now=datetime(2026, 5, 18, 9, 50))
    duplicate = engine.run(now=datetime(2026, 5, 18, 9, 50))
    next_day = engine.run(now=datetime(2026, 5, 19, 9, 50))

    assert first["status"] == "completed"
    assert duplicate["status"] == "skipped"
    assert duplicate["reason"] == "duplicate_scheduled_run"
    assert duplicate["state"]["count"] == 1
    assert duplicate["portfolio"]["available_cash"] == 99_990
    assert next_day["state"]["count"] == 2


def test_run_weekly_and_monthly_use_trade_calendar(tmp_path):
    strategy_path = tmp_path / "calendar_scheduled_strategy.py"
    strategy_path.write_text(
        "from jqdata import *\n"
        "\n"
        "def initialize(context):\n"
        "    g.weekly = getattr(g, 'weekly', 0)\n"
        "    g.monthly = getattr(g, 'monthly', 0)\n"
        "    run_weekly(weekly, 1, '09:50')\n"
        "    run_monthly(monthly, -1, '09:50')\n"
        "\n"
        "def weekly(context):\n"
        "    g.weekly += 1\n"
        "\n"
        "def monthly(context):\n"
        "    g.monthly += 1\n",
        encoding="utf-8",
    )
    engine = RuntimeEngine(
        strategy_id="calendar_scheduled",
        strategy_path=strategy_path,
        data=StaticMarketDataProvider(trade_days=["2026-05-18", "2026-05-19", "2026-05-25", "2026-05-29"]),
        broker=PaperBroker(),
        state_store=MemoryStateStore(),
        notifier=ConsoleNotifier(),
        initial_cash=100_000,
    )

    weekly = engine.run(now=datetime(2026, 5, 18, 9, 50))
    monthly = engine.run(now=datetime(2026, 5, 29, 9, 50))

    assert weekly["state"] == {"weekly": 1, "monthly": 0}
    assert monthly["state"] == {"weekly": 1, "monthly": 1}


def test_lifecycle_hooks_run_around_due_jobs(tmp_path):
    strategy_path = tmp_path / "lifecycle_strategy.py"
    strategy_path.write_text(
        "from jqdata import *\n"
        "\n"
        "def initialize(context):\n"
        "    g.events = getattr(g, 'events', [])\n"
        "    run_daily(trade, '09:50')\n"
        "\n"
        "def before_trading_start(context):\n"
        "    g.events.append('before')\n"
        "\n"
        "def trade(context):\n"
        "    g.events.append('trade')\n"
        "\n"
        "def after_trading_end(context):\n"
        "    g.events.append('after')\n",
        encoding="utf-8",
    )
    engine = RuntimeEngine(
        strategy_id="lifecycle",
        strategy_path=strategy_path,
        data=EmptyMarketDataProvider(),
        broker=PaperBroker(),
        state_store=MemoryStateStore(),
        notifier=ConsoleNotifier(),
        initial_cash=100_000,
    )

    result = engine.run(now=datetime(2026, 5, 18, 9, 50))

    assert result["state"]["events"] == ["before", "trade", "after"]
    assert result["due_jobs"] == ["before_trading_start", "trade", "after_trading_end"]


def test_paper_broker_uses_market_price_costs_and_persists_order_history(tmp_path):
    strategy_path = tmp_path / "priced_strategy.py"
    strategy_path.write_text(
        "from jqdata import *\n"
        "\n"
        "def initialize(context):\n"
        "    set_slippage(FixedSlippage(0.5))\n"
        "    set_order_cost(OrderCost(open_commission=0.001, close_commission=0.001, min_commission=1))\n"
        "    run_daily(trade, '09:50')\n"
        "\n"
        "def trade(context):\n"
        "    order_target_value('000001.XSHE', 105)\n",
        encoding="utf-8",
    )
    data = StaticMarketDataProvider(current=["000001.XSHE"])
    data.current["000001.XSHE"] = CurrentData("000001.XSHE", last_price=10.0)
    engine = RuntimeEngine(
        strategy_id="priced",
        strategy_path=strategy_path,
        data=data,
        broker=PaperBroker(),
        state_store=MemoryStateStore(),
        notifier=ConsoleNotifier(),
        initial_cash=1_000,
    )

    result = engine.run(now=datetime(2026, 5, 18, 9, 50))

    assert result["orders"][0]["price"] == 10.5
    assert result["orders"][0]["commission"] == 1
    assert result["portfolio"]["available_cash"] == 894
    assert result["portfolio"]["positions"]["000001.XSHE"]["total_amount"] == 10


def test_failed_run_persists_failure_metadata_without_duplicate_completion(tmp_path):
    strategy_path = tmp_path / "failing_persistent_strategy.py"
    strategy_path.write_text(
        "from jqdata import *\n"
        "\n"
        "def initialize(context):\n"
        "    run_daily(trade, '09:50')\n"
        "\n"
        "def trade(context):\n"
        "    raise RuntimeError('boom')\n",
        encoding="utf-8",
    )
    store = MemoryStateStore()
    engine = RuntimeEngine(
        strategy_id="failing_persistent",
        strategy_path=strategy_path,
        data=EmptyMarketDataProvider(),
        broker=PaperBroker(),
        state_store=store,
        notifier=ConsoleNotifier(),
        initial_cash=100_000,
    )

    first = engine.run(now=datetime(2026, 5, 18, 9, 50))
    retry = engine.run(now=datetime(2026, 5, 18, 9, 50))

    assert first["status"] == "failed"
    assert first["metadata"]["last_status"] == "failed"
    assert first["metadata"]["last_error"] == {"type": "RuntimeError", "message": "boom"}
    assert retry["status"] == "failed"


def test_runtime_returns_failed_status_and_notifies(tmp_path):
    class CaptureNotifier:
        def __init__(self):
            self.messages = []

        def send(self, subject, message):
            self.messages.append((subject, message))

    strategy_path = tmp_path / "failing_strategy.py"
    strategy_path.write_text(
        "from jqdata import *\n"
        "\n"
        "def initialize(context):\n"
        "    run_daily(trade, '09:50')\n"
        "\n"
        "def trade(context):\n"
        "    raise RuntimeError('boom')\n",
        encoding="utf-8",
    )
    notifier = CaptureNotifier()
    engine = RuntimeEngine(
        strategy_id="failing",
        strategy_path=strategy_path,
        data=EmptyMarketDataProvider(),
        broker=PaperBroker(),
        state_store=MemoryStateStore(),
        notifier=notifier,
        initial_cash=100_000,
    )

    result = engine.run(now=datetime(2026, 5, 18, 9, 50))

    assert result["status"] == "failed"
    assert result["error"] == {"type": "RuntimeError", "message": "boom"}
    assert notifier.messages
    assert "failed" in notifier.messages[0][0]
    assert "RuntimeError: boom" in notifier.messages[0][1]


def test_context_previous_date_uses_trade_calendar(tmp_path):
    strategy_path = tmp_path / "calendar_strategy.py"
    strategy_path.write_text(
        "from jqdata import *\n"
        "\n"
        "def initialize(context):\n"
        "    run_daily(record, '09:50')\n"
        "\n"
        "def record(context):\n"
        "    g.previous_date = context.previous_date.isoformat()\n",
        encoding="utf-8",
    )
    engine = RuntimeEngine(
        strategy_id="calendar",
        strategy_path=strategy_path,
        data=StaticMarketDataProvider(trade_days=["2026-05-14", "2026-05-15", "2026-05-18"]),
        broker=PaperBroker(),
        state_store=MemoryStateStore(),
        notifier=ConsoleNotifier(),
        initial_cash=100_000,
    )

    result = engine.run(now=datetime(2026, 5, 18, 9, 50))

    assert result["state"]["previous_date"] == "2026-05-15"


def test_lambda_event_time_parses_eventbridge_time():
    result = _event_time({"time": "2026-05-18T01:50:00Z"})

    assert result.isoformat() == "2026-05-18T01:50:00+00:00"
