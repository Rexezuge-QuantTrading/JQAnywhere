from datetime import datetime
from pathlib import Path

from jqanywhere.broker.paper import PaperBroker
from jqanywhere.data.base import EmptyMarketDataProvider, StaticMarketDataProvider
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
        assert "v0.3" in str(exc)
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
