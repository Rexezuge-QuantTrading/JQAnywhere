"""JoinQuant-compatible public API subset."""

from __future__ import annotations

from jqanywhere.jqcompat.types import *
from jqanywhere.runtime.state import get_session

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - dependency is installed in normal package usage.
    np = None


def set_benchmark(security: str) -> None:
    get_session().benchmark = security


def set_option(key: str, value) -> None:
    get_session().options[key] = value


def set_order_cost(cost: OrderCost, type="stock", ref=None) -> None:
    get_session().order_cost = cost


def set_commission(cost: PerTrade) -> None:
    get_session().order_cost = cost


def set_slippage(obj: FixedSlippage, type=None, ref=None) -> None:
    get_session().slippage = obj


def run_daily(func, time: str, reference_security: str = "") -> None:
    get_session().scheduler.run_daily(func, time, reference_security)


def run_weekly(func, weekday: int, time: str, reference_security: str = "") -> None:
    get_session().scheduler.run_weekly(func, weekday, time, reference_security)


def run_monthly(func, monthday: int, time: str, reference_security: str = "") -> None:
    get_session().scheduler.run_monthly(func, monthday, time, reference_security)


def attribute_history(
    security: str,
    count: int,
    unit: str = "1d",
    fields=("open", "close", "high", "low", "volume", "money"),
    skip_paused: bool = True,
    df: bool = True,
    fq: str | None = "pre",
):
    return get_session().data.attribute_history(security, count, unit, fields, skip_paused, df, fq)


def get_current_data():
    return get_session().data.get_current_data()


def order_target_value(security: str, value: float, style=MarketOrderStyle, side: str = "long", pindex: int = 0, close_today: bool = False):
    session = get_session()
    order_result = session.broker.order_target_value(
        session.context, security, value, style=style, side=side, pindex=pindex, close_today=close_today
    )
    session.log.info(f"order_target_value({security}, {value}) -> {order_result}")
    return order_result


def order_target(security: str, amount: int, style=MarketOrderStyle, side: str = "long", pindex: int = 0, close_today: bool = False):
    session = get_session()
    order_result = session.broker.order_target(
        session.context, security, amount, style=style, side=side, pindex=pindex, close_today=close_today
    )
    session.log.info(f"order_target({security}, {amount}) -> {order_result}")
    return order_result


def order(security: str, amount: int, style=MarketOrderStyle, side: str = "long", pindex: int = 0, close_today: bool = False):
    session = get_session()
    order_result = session.broker.order(session.context, security, amount, style=style, side=side, pindex=pindex, close_today=close_today)
    session.log.info(f"order({security}, {amount}) -> {order_result}")
    return order_result


def order_value(security: str, value: float, style=MarketOrderStyle, side: str = "long", pindex: int = 0, close_today: bool = False):
    session = get_session()
    order_result = session.broker.order_value(
        session.context, security, value, style=style, side=side, pindex=pindex, close_today=close_today
    )
    session.log.info(f"order_value({security}, {value}) -> {order_result}")
    return order_result


def get_price(*args, **kwargs):
    return get_session().data.get_price(*args, **kwargs)


def get_index_stocks(*args, **kwargs):
    return get_session().data.get_index_stocks(*args, **kwargs)


def get_all_securities(*args, **kwargs):
    return get_session().data.get_all_securities(*args, **kwargs)


def get_security_info(*args, **kwargs):
    return get_session().data.get_security_info(*args, **kwargs)


def get_trade_days(*args, **kwargs):
    return get_session().data.get_trade_days(*args, **kwargs)


def get_all_trade_days(*args, **kwargs):
    return get_session().data.get_all_trade_days(*args, **kwargs)


def unsupported(name: str):
    raise NotImplementedError(f"JQAnywhere v0.5 does not support {name}")


def handle_data(*args, **kwargs):
    unsupported("handle_data")


def before_trading_start(*args, **kwargs):
    unsupported("before_trading_start")


def after_trading_end(*args, **kwargs):
    unsupported("after_trading_end")


def get_fundamentals(*args, **kwargs):
    unsupported("get_fundamentals")


def query(*args, **kwargs):
    unsupported("query/fundamentals DSL")


class _UnsupportedTable:
    def __getattr__(self, name):
        unsupported(f"fundamentals field {name}")


class _UnsupportedNamespace:
    def __init__(self, name: str):
        self.name = name

    def run_query(self, *args, **kwargs):
        unsupported(f"{self.name}.run_query")

    def __getattr__(self, name):
        unsupported(f"{self.name}.{name}")


valuation = _UnsupportedTable()
balance = _UnsupportedTable()
cash_flow = _UnsupportedTable()
income = _UnsupportedTable()
indicator = _UnsupportedTable()
finance = _UnsupportedNamespace("finance")
macro = _UnsupportedNamespace("macro")


def get_factor_values(*args, **kwargs):
    unsupported("factor APIs")


def get_factors(*args, **kwargs):
    unsupported("factor APIs")


def get_all_factors(*args, **kwargs):
    unsupported("factor APIs")


def portfolio_optimizer(*args, **kwargs):
    unsupported("portfolio optimizer")


__all__ = [name for name in globals() if not name.startswith("_")]
