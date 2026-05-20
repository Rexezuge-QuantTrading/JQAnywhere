import importlib
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

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
    with pytest.raises(NotImplementedError, match="v0.8.0"):
        EmptyMarketDataProvider().get_fundamentals(None)


def test_strategy_import_dependencies_are_available():
    jqfactor = importlib.import_module("jqfactor")
    PrettyTable = importlib.import_module("prettytable").PrettyTable
    talib = importlib.import_module("talib")

    assert jqfactor.__all__ == ["get_all_factors", "get_factor_values", "get_factors"]
    high = np.array([2, 3, 4], dtype=float)
    low = np.array([1, 2, 3], dtype=float)
    close = np.array([1.5, 2.5, 3.5], dtype=float)
    assert talib.ATR(high, low, close, timeperiod=2)[-1] > 0
    assert talib.SMA(close, timeperiod=2)[-1] == 3
    table = PrettyTable()
    table.field_names = ["code"]
    table.add_row(["000001.XSHE"])
    assert "000001.XSHE" in str(table)


def test_run_daily_accepts_safe_schedule_aliases(tmp_path):
    strategy_path = tmp_path / "alias_strategy.py"
    strategy_path.write_text(
        "from jqdata import *\n"
        "\n"
        "def initialize(context):\n"
        "    g.events = getattr(g, 'events', [])\n"
        "    run_daily(open_trade, 'open')\n"
        "    run_daily(close_trade, 'close')\n"
        "\n"
        "def open_trade(context):\n"
        "    g.events.append('open')\n"
        "\n"
        "def close_trade(context):\n"
        "    g.events.append('close')\n",
        encoding="utf-8",
    )
    engine = RuntimeEngine(
        strategy_id="alias",
        strategy_path=strategy_path,
        data=EmptyMarketDataProvider(),
        broker=PaperBroker(),
        state_store=MemoryStateStore(),
        notifier=ConsoleNotifier(),
        initial_cash=100_000,
    )

    morning = engine.run(now=datetime(2026, 5, 18, 9, 30))
    close = engine.run(now=datetime(2026, 5, 18, 15, 0))

    assert morning["state"]["events"] == ["open"]
    assert close["state"]["events"] == ["open", "close"]


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


def test_run_daily_every_bar_runs_during_trading_minutes(tmp_path):
    strategy_path = tmp_path / "every_bar_strategy.py"
    strategy_path.write_text(
        "from jqdata import *\n"
        "\n"
        "def initialize(context):\n"
        "    g.count = getattr(g, 'count', 0)\n"
        "    run_daily(trade, 'every_bar')\n"
        "\n"
        "def trade(context):\n"
        "    g.count += 1\n",
        encoding="utf-8",
    )
    engine = RuntimeEngine(
        strategy_id="every_bar",
        strategy_path=strategy_path,
        data=EmptyMarketDataProvider(),
        broker=PaperBroker(),
        state_store=MemoryStateStore(),
        notifier=ConsoleNotifier(),
        initial_cash=100_000,
    )

    before_open = engine.run(now=datetime(2026, 5, 18, 9, 29))
    open_bar = engine.run(now=datetime(2026, 5, 18, 9, 30))
    lunch_break = engine.run(now=datetime(2026, 5, 18, 11, 30))
    afternoon_bar = engine.run(now=datetime(2026, 5, 18, 13, 0))

    assert before_open["state"]["count"] == 0
    assert open_bar["state"]["count"] == 1
    assert lunch_break["state"]["count"] == 1
    assert afternoon_bar["state"]["count"] == 2


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


def test_v08_query_records_static_provider_and_reference_data(tmp_path):
    strategy_path = tmp_path / "v08_strategy.py"
    strategy_path.write_text(
        "from jqdata import *\n"
        "\n"
        "def initialize(context):\n"
        "    run_daily(scan, '09:50')\n"
        "\n"
        "def scan(context):\n"
        "    q = (query(valuation.code, valuation.market_cap)\n"
        "        .filter(valuation.code.in_(['000001.XSHE', '000002.XSHE']),\n"
        "                valuation.market_cap.between(5, 60),\n"
        "                cash_flow.subtotal_operate_cash_inflow / indicator.adjusted_profit > 2)\n"
        "        .order_by(valuation.market_cap.asc())\n"
        "        .limit(1))\n"
        "    df = get_fundamentals(q)\n"
        "    g.pick = df.code.iloc[0]\n"
        "    g.cap = float(get_valuation(g.pick, fields=['circulating_cap']).iloc[0]['circulating_cap'])\n"
        "    g.industry = get_industry([g.pick])[g.pick]['sw_l2']['industry_name']\n"
        "    g.nav = float(get_extras('unit_net_value', '510300.XSHG', count=1).iloc[-1, 0])\n"
        "    g.run_type = context.run_params.type\n"
        "    record(pick=g.pick, nav=g.nav)\n",
        encoding="utf-8",
    )
    fundamentals = pd.DataFrame(
        [
            {
                "code": "000001.XSHE",
                "market_cap": 20.0,
                "circulating_cap": 3.0,
                "subtotal_operate_cash_inflow": 10.0,
                "adjusted_profit": 3.0,
            },
            {
                "code": "000002.XSHE",
                "market_cap": 10.0,
                "circulating_cap": 2.0,
                "subtotal_operate_cash_inflow": 1.0,
                "adjusted_profit": 1.0,
            },
        ]
    )
    data = StaticMarketDataProvider(
        fundamentals=fundamentals,
        industry={"000001.XSHE": {"sw_l2": {"industry_name": "银行", "industry_code": "801780"}}},
        extras={"unit_net_value": {"510300.XSHG": 4.25}},
    )
    engine = RuntimeEngine(
        strategy_id="v08",
        strategy_path=strategy_path,
        data=data,
        broker=PaperBroker(),
        state_store=MemoryStateStore(),
        notifier=ConsoleNotifier(),
        initial_cash=100_000,
    )

    result = engine.run(now=datetime(2026, 5, 18, 9, 50))

    assert result["state"] == {"pick": "000001.XSHE", "cap": 3.0, "industry": "银行", "nav": 4.25, "run_type": "sim_trade"}
    assert result["records"] == [{"time": "2026-05-18T09:50:00+08:00", "pick": "000001.XSHE", "nav": 4.25}]


def test_context_run_params_exposes_v08_end_date_shim(tmp_path):
    strategy_path = tmp_path / "run_params_strategy.py"
    strategy_path.write_text(
        "from jqdata import *\n"
        "\n"
        "def initialize(context):\n"
        "    run_daily(trade, '15:30')\n"
        "\n"
        "def trade(context):\n"
        "    g.end_date = context.run_params.end_date.isoformat()\n"
        "    g.frequency = context.run_params.frequency\n",
        encoding="utf-8",
    )
    engine = RuntimeEngine(
        strategy_id="run_params",
        strategy_path=strategy_path,
        data=EmptyMarketDataProvider(),
        broker=PaperBroker(),
        state_store=MemoryStateStore(),
        notifier=ConsoleNotifier(),
        initial_cash=100_000,
    )

    result = engine.run(now=datetime(2026, 5, 18, 15, 30))

    assert result["state"] == {"end_date": "2026-05-18", "frequency": "minute"}


def test_history_and_order_status_match_joinquant_style(tmp_path):
    strategy_path = tmp_path / "history_order_strategy.py"
    strategy_path.write_text(
        "from jqdata import *\n"
        "\n"
        "def initialize(context):\n"
        "    run_daily(trade, '09:50')\n"
        "\n"
        "def trade(context):\n"
        "    prices = history(1, unit='1d', field='close', security_list=['000001.XSHE'])\n"
        "    g.last_close = float(prices['000001.XSHE'][-1])\n"
        "    order = order_target_value('000001.XSHE', 100)\n"
        "    g.held_status = order.status == OrderStatus.held\n"
        "    g.filled = order.filled\n",
        encoding="utf-8",
    )
    data = StaticMarketDataProvider(
        history={"000001.XSHE": pd.DataFrame({"close": [10.0]}, index=pd.to_datetime(["2026-05-15"]))},
        current=["000001.XSHE"],
    )
    data.current["000001.XSHE"].last_price = 10.0
    engine = RuntimeEngine(
        strategy_id="history_order",
        strategy_path=strategy_path,
        data=data,
        broker=PaperBroker(),
        state_store=MemoryStateStore(),
        notifier=ConsoleNotifier(),
        initial_cash=1_000,
    )

    result = engine.run(now=datetime(2026, 5, 18, 9, 50))

    assert result["state"] == {"last_close": 10.0, "held_status": True, "filled": 10}
    assert result["orders"][0]["filled"] == 10


def test_history_defaults_to_avg_and_keeps_datetime_index(tmp_path):
    strategy_path = tmp_path / "history_defaults_strategy.py"
    strategy_path.write_text(
        "from jqdata import *\n"
        "\n"
        "def initialize(context):\n"
        "    run_daily(trade, '09:50')\n"
        "\n"
        "def trade(context):\n"
        "    prices = history(1, security_list=['000001.XSHE'])\n"
        "    g.columns = list(prices.columns)\n"
        "    g.index = str(prices.index[0].date())\n"
        "    g.value = float(prices['000001.XSHE'].iloc[0])\n",
        encoding="utf-8",
    )
    data = StaticMarketDataProvider(
        history={"000001.XSHE": pd.DataFrame({"avg": [10.5]}, index=pd.to_datetime(["2026-05-15"]))},
        current=["000001.XSHE"],
    )
    engine = RuntimeEngine(
        strategy_id="history_defaults",
        strategy_path=strategy_path,
        data=data,
        broker=PaperBroker(),
        state_store=MemoryStateStore(),
        notifier=ConsoleNotifier(),
        initial_cash=1_000,
    )

    result = engine.run(now=datetime(2026, 5, 18, 9, 50))

    assert result["state"] == {"columns": ["000001.XSHE"], "index": "2026-05-15", "value": 10.5}


def test_fundamentals_query_equality_table_projection_and_reuse(tmp_path):
    strategy_path = tmp_path / "query_regression_strategy.py"
    strategy_path.write_text(
        "from jqdata import *\n"
        "\n"
        "def initialize(context):\n"
        "    run_daily(scan, '09:50')\n"
        "\n"
        "def scan(context):\n"
        "    base = query(valuation.code, valuation.market_cap)\n"
        "    q1 = base.filter(valuation.code == '000001.XSHE')\n"
        "    q2 = base.filter(valuation.code == '000002.XSHE')\n"
        "    g.pick1 = get_fundamentals(q1).code.iloc[0]\n"
        "    g.pick2 = get_fundamentals(q2).code.iloc[0]\n"
        "    table_df = get_fundamentals(query(valuation))\n"
        "    g.table_columns = list(table_df.columns)\n",
        encoding="utf-8",
    )
    fundamentals = pd.DataFrame(
        [
            {"code": "000001.XSHE", "market_cap": 20.0},
            {"code": "000002.XSHE", "market_cap": 10.0},
        ]
    )
    engine = RuntimeEngine(
        strategy_id="query_regression",
        strategy_path=strategy_path,
        data=StaticMarketDataProvider(fundamentals=fundamentals),
        broker=PaperBroker(),
        state_store=MemoryStateStore(),
        notifier=ConsoleNotifier(),
        initial_cash=100_000,
    )

    result = engine.run(now=datetime(2026, 5, 18, 9, 50))

    assert result["state"] == {"pick1": "000001.XSHE", "pick2": "000002.XSHE", "table_columns": ["code", "market_cap"]}


def test_get_valuation_supports_official_signature_defaults_and_dates():
    fundamentals = pd.DataFrame(
        [
            {"code": "000001.XSHE", "day": "2026-05-14", "market_cap": 10.0},
            {"code": "000001.XSHE", "day": "2026-05-15", "market_cap": 11.0},
        ]
    )
    data = StaticMarketDataProvider(fundamentals=fundamentals)

    result = data.get_valuation("000001.XSHE", start_date="2026-05-15", end_date="2026-05-15")

    assert list(result.columns) == [
        "code",
        "day",
        "capitalization",
        "circulating_cap",
        "market_cap",
        "circulating_market_cap",
        "turnover_ratio",
        "pe_ratio",
        "pe_ratio_lyr",
        "pb_ratio",
        "ps_ratio",
        "pcf_ratio",
    ]
    assert result["day"].tolist() == ["2026-05-15"]
    assert result["market_cap"].tolist() == [11.0]


def test_paper_broker_uses_asset_type_specific_costs_and_slippage(tmp_path):
    strategy_path = tmp_path / "asset_cost_strategy.py"
    strategy_path.write_text(
        "from jqdata import *\n"
        "\n"
        "def initialize(context):\n"
        "    set_slippage(FixedSlippage(0.5), type='stock')\n"
        "    set_slippage(FixedSlippage(0.1), type='fund')\n"
        "    set_order_cost(OrderCost(open_commission=0.1, min_commission=1), type='stock')\n"
        "    set_order_cost(OrderCost(open_commission=0.0, min_commission=0), type='fund')\n"
        "    run_daily(trade, '09:50')\n"
        "\n"
        "def trade(context):\n"
        "    order_target_value('510300.XSHG', 100)\n",
        encoding="utf-8",
    )
    data = StaticMarketDataProvider(current=["510300.XSHG"])
    data.current["510300.XSHG"].last_price = 10.0
    engine = RuntimeEngine(
        strategy_id="asset_cost",
        strategy_path=strategy_path,
        data=data,
        broker=PaperBroker(),
        state_store=MemoryStateStore(),
        notifier=ConsoleNotifier(),
        initial_cash=1_000,
    )

    result = engine.run(now=datetime(2026, 5, 18, 9, 50))

    assert result["orders"][0]["price"] == 10.1
    assert result["orders"][0]["commission"] == 0


def test_paper_broker_uses_ref_slippage_and_close_today_commission(tmp_path):
    strategy_path = tmp_path / "ref_cost_strategy.py"
    strategy_path.write_text(
        "from jqdata import *\n"
        "\n"
        "def initialize(context):\n"
        "    g.count = getattr(g, 'count', 0)\n"
        "    set_slippage(PriceRelatedSlippage(0.1), ref='000001.XSHE')\n"
        "    set_order_cost(OrderCost(close_commission=0.01, close_today_commission=0.02), ref='000001.XSHE')\n"
        "    run_daily(trade, '09:50')\n"
        "\n"
        "def trade(context):\n"
        "    if g.count == 0:\n"
        "        order_target_value('000001.XSHE', 100)\n"
        "    else:\n"
        "        order_target_value('000001.XSHE', 0, close_today=True)\n"
        "    g.count += 1\n",
        encoding="utf-8",
    )
    data = StaticMarketDataProvider(current=["000001.XSHE"])
    data.current["000001.XSHE"].last_price = 10.0
    engine = RuntimeEngine(
        strategy_id="ref_cost",
        strategy_path=strategy_path,
        data=data,
        broker=PaperBroker(),
        state_store=MemoryStateStore(),
        notifier=ConsoleNotifier(),
        initial_cash=1_000,
    )

    first = engine.run(now=datetime(2026, 5, 18, 9, 50))
    result = engine.run(now=datetime(2026, 5, 19, 9, 50))

    assert first["orders"][0]["price"] == 11.0
    assert result["orders"][1]["price"] == 9.0
    assert result["orders"][1]["commission"] == 1.8
    assert result["orders"][1]["status"] == "held"


def test_paper_broker_rejected_order_returns_none_to_strategy(tmp_path):
    strategy_path = tmp_path / "rejected_order_strategy.py"
    strategy_path.write_text(
        "from jqdata import *\n"
        "\n"
        "def initialize(context):\n"
        "    run_daily(trade, '09:50')\n"
        "\n"
        "def trade(context):\n"
        "    g.order_is_none = order('000001.XSHE', -10) is None\n",
        encoding="utf-8",
    )
    engine = RuntimeEngine(
        strategy_id="rejected_order",
        strategy_path=strategy_path,
        data=EmptyMarketDataProvider(),
        broker=PaperBroker(),
        state_store=MemoryStateStore(),
        notifier=ConsoleNotifier(),
        initial_cash=1_000,
    )

    result = engine.run(now=datetime(2026, 5, 18, 9, 50))

    assert result["state"] == {"order_is_none": True}
    assert result["orders"][0]["status"] == "rejected"


def test_paper_broker_keeps_same_day_buys_non_closeable(tmp_path):
    strategy_path = tmp_path / "t1_strategy.py"
    strategy_path.write_text(
        "from jqdata import *\n"
        "\n"
        "def initialize(context):\n"
        "    g.count = getattr(g, 'count', 0)\n"
        "    run_daily(trade, '09:50')\n"
        "\n"
        "def trade(context):\n"
        "    if g.count == 0:\n"
        "        order_target_value('000001.XSHE', 100)\n"
        "        g.same_day_closeable = context.portfolio.positions['000001.XSHE'].closeable_amount\n"
        "    else:\n"
        "        g.next_day_closeable = context.portfolio.positions['000001.XSHE'].closeable_amount\n"
        "    g.count += 1\n",
        encoding="utf-8",
    )
    data = StaticMarketDataProvider(current=["000001.XSHE"])
    data.current["000001.XSHE"].last_price = 10.0
    engine = RuntimeEngine(
        strategy_id="t1",
        strategy_path=strategy_path,
        data=data,
        broker=PaperBroker(),
        state_store=MemoryStateStore(),
        notifier=ConsoleNotifier(),
        initial_cash=1_000,
    )

    first = engine.run(now=datetime(2026, 5, 18, 9, 50))
    second = engine.run(now=datetime(2026, 5, 19, 9, 50))

    assert first["state"]["same_day_closeable"] == 0
    assert second["state"]["next_day_closeable"] == 10


def test_order_management_apis_are_available(tmp_path):
    strategy_path = tmp_path / "order_management_strategy.py"
    strategy_path.write_text(
        "from jqdata import *\n"
        "\n"
        "def initialize(context):\n"
        "    run_daily(trade, '09:50')\n"
        "\n"
        "def trade(context):\n"
        "    order = order_target_value('000001.XSHE', 100)\n"
        "    g.order_id = order.order_id\n"
        "    g.orders_count = len(get_orders())\n"
        "    g.security_orders_count = len(get_orders(security='000001.XSHE'))\n"
        "    g.open_orders_count = len(get_open_orders())\n"
        "    g.trades_count = len(get_trades())\n",
        encoding="utf-8",
    )
    data = StaticMarketDataProvider(current=["000001.XSHE"])
    data.current["000001.XSHE"].last_price = 10.0
    engine = RuntimeEngine(
        strategy_id="order_management",
        strategy_path=strategy_path,
        data=data,
        broker=PaperBroker(),
        state_store=MemoryStateStore(),
        notifier=ConsoleNotifier(),
        initial_cash=1_000,
    )

    result = engine.run(now=datetime(2026, 5, 18, 9, 50))

    assert result["state"] == {
        "order_id": "paper-1",
        "orders_count": 1,
        "security_orders_count": 1,
        "open_orders_count": 0,
        "trades_count": 0,
    }


def test_paper_broker_marks_positions_to_current_price_across_runs(tmp_path):
    strategy_path = tmp_path / "mark_to_market_strategy.py"
    strategy_path.write_text(
        "from jqdata import *\n"
        "\n"
        "def initialize(context):\n"
        "    g.count = getattr(g, 'count', 0)\n"
        "    run_daily(trade, '09:50')\n"
        "\n"
        "def trade(context):\n"
        "    if g.count == 0:\n"
        "        order_target_value('000001.XSHE', 100)\n"
        "    else:\n"
        "        g.value = context.portfolio.total_value\n"
        "    g.count += 1\n",
        encoding="utf-8",
    )
    data = StaticMarketDataProvider(current=["000001.XSHE"])
    data.current["000001.XSHE"].last_price = 10.0
    engine = RuntimeEngine(
        strategy_id="mark_to_market",
        strategy_path=strategy_path,
        data=data,
        broker=PaperBroker(),
        state_store=MemoryStateStore(),
        notifier=ConsoleNotifier(),
        initial_cash=1_000,
    )

    first = engine.run(now=datetime(2026, 5, 18, 9, 50))
    data.current["000001.XSHE"].last_price = 20.0
    second = engine.run(now=datetime(2026, 5, 19, 9, 50))

    assert first["portfolio_value"] == 1_000
    assert second["state"]["value"] == 1_100
    assert second["portfolio"]["positions"]["000001.XSHE"]["value"] == 200


def test_paper_broker_rejects_unavailable_sell(tmp_path):
    strategy_path = tmp_path / "sell_rejection_strategy.py"
    strategy_path.write_text(
        "from jqdata import *\n"
        "\n"
        "def initialize(context):\n"
        "    run_daily(trade, '09:50')\n"
        "\n"
        "def trade(context):\n"
        "    order('000001.XSHE', -10)\n",
        encoding="utf-8",
    )
    engine = RuntimeEngine(
        strategy_id="sell_rejection",
        strategy_path=strategy_path,
        data=EmptyMarketDataProvider(),
        broker=PaperBroker(),
        state_store=MemoryStateStore(),
        notifier=ConsoleNotifier(),
        initial_cash=1_000,
    )

    result = engine.run(now=datetime(2026, 5, 18, 9, 50))

    assert result["orders"][0]["status"] == "rejected"
    assert result["orders"][0]["reason"] == "insufficient_position"


def test_memory_store_recovers_older_active_run_key():
    store = MemoryStateStore()
    store.save("stale", {"metadata": {"revision": 1, "active_run_key": "2026-05-18T09:50:00+08:00"}})

    claim = store.claim_run("stale", {"metadata": {"revision": 1}}, "2026-05-19T09:50:00+08:00")
    duplicate = store.claim_run("stale", claim.state, "2026-05-19T09:50:00+08:00")

    assert claim.claimed is True
    assert claim.state["metadata"]["active_run_key"] == "2026-05-19T09:50:00+08:00"
    assert duplicate.claimed is False


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
