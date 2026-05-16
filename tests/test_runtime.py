from pathlib import Path

from jqanywhere.broker.paper import PaperBroker
from jqanywhere.data.base import EmptyMarketDataProvider
from jqanywhere.notifications.console import ConsoleNotifier
from jqanywhere.persistence.memory import MemoryStateStore
from jqanywhere.runtime.engine import RuntimeEngine


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

    result = engine.run()

    assert result["status"] == "completed"
    assert result["portfolio_value"] == 100_000
    assert "order_target_value" in result["logs"]


def test_unsupported_fundamentals_is_explicit():
    from jqanywhere.jqcompat.api import get_fundamentals

    try:
        get_fundamentals(None)
    except NotImplementedError as exc:
        assert "v0.1" in str(exc)
    else:
        raise AssertionError("get_fundamentals should be unsupported")
