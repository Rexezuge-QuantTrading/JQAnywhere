"""JoinQuant-compatible public API subset."""

from __future__ import annotations

import pandas as pd

from jqanywhere.jqcompat.query import balance, cash_flow, income, indicator, query, valuation
from jqanywhere.jqcompat.types import *
from jqanywhere.runtime.state import get_session

_QUERY_EXPORTS = (balance, cash_flow, income, indicator, query, valuation)

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - dependency is installed in normal package usage.
    np = None


def set_benchmark(security: str) -> None:
    get_session().benchmark = security


def set_option(key: str, value) -> None:
    get_session().options[key] = value


def set_order_cost(cost: OrderCost, type="stock", ref=None) -> None:
    session = get_session()
    cost.type = type
    cost.ref = ref
    session.order_cost = cost
    if ref is not None:
        session.order_costs[str(ref)] = cost
    if type is not None:
        session.order_costs[str(type)] = cost


def set_commission(cost: PerTrade) -> None:
    session = get_session()
    session.order_cost = cost
    session.order_costs["default"] = cost


def set_slippage(obj: FixedSlippage, type=None, ref=None) -> None:
    session = get_session()
    session.slippage = obj
    if ref is not None:
        session.slippages[str(ref)] = obj
    if type is not None:
        session.slippages[str(type)] = obj


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
    result = get_session().data.attribute_history(security, count, unit, fields, skip_paused, df, fq)
    return _jq_dataframe(result) if df else result


def get_current_data():
    return get_session().data.get_current_data()


def history(
    count: int,
    unit: str = "1d",
    field: str = "avg",
    security_list=None,
    df: bool = True,
    skip_paused: bool = False,
    fq: str | None = "pre",
):
    session = get_session()
    securities = (
        _portfolio_securities() if security_list is None else ([security_list] if isinstance(security_list, str) else list(security_list))
    )
    if not securities:
        return pd.DataFrame() if df else {}
    frames = {}
    for security in securities:
        data = session.data.attribute_history(security, count, unit, [field], skip_paused, True, fq)
        frames[security] = data[field] if field in data else pd.Series(dtype=float)
    result = _JoinQuantDataFrame(frames)
    return result if df else {security: result[security].to_numpy() for security in result.columns}


def record(**kwargs) -> None:
    session = get_session()
    session.records.append({"time": session.context.current_dt.isoformat(), **kwargs})


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


def cancel_order(order) -> Order | None:
    target = _order_from_any(order)
    if target is None:
        return None
    if target.status in {OrderStatus.new, OrderStatus.open}:
        target.status = OrderStatus.canceled
    return target


def get_open_orders() -> dict[str, Order]:
    return {order_id: order for order_id, order in get_orders().items() if order.status in {OrderStatus.new, OrderStatus.open}}


def get_orders(order_id: str = None, security: str = None, status: OrderStatus = None) -> dict[str, Order]:
    orders = {}
    for index, item in enumerate(get_session().context.order_history, 1):
        order = _order_from_any(item)
        if order is None:
            continue
        key = order.order_id or str(item.get("order_id") or item.get("client_order_id") or index)
        if order_id is not None and key != order_id:
            continue
        if security is not None and order.security != security:
            continue
        if status is not None and order.status != status:
            continue
        orders[key] = order
    return orders


def get_trades() -> dict:
    return {}


def get_price(*args, **kwargs):
    return get_session().data.get_price(*args, **kwargs)


def get_fundamentals(*args, **kwargs):
    return get_session().data.get_fundamentals(*args, **kwargs)


def get_valuation(*args, **kwargs):
    return get_session().data.get_valuation(*args, **kwargs)


def get_industry(*args, **kwargs):
    return get_session().data.get_industry(*args, **kwargs)


def get_extras(*args, **kwargs):
    return get_session().data.get_extras(*args, **kwargs)


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
    raise NotImplementedError(f"JQAnywhere v0.8.0 does not support {name}")


def handle_data(*args, **kwargs):
    unsupported("handle_data")


def before_trading_start(*args, **kwargs):
    unsupported("before_trading_start")


def after_trading_end(*args, **kwargs):
    unsupported("after_trading_end")


class _UnsupportedNamespace:
    def __init__(self, name: str):
        self.name = name

    def run_query(self, *args, **kwargs):
        unsupported(f"{self.name}.run_query")

    def __getattr__(self, name):
        unsupported(f"{self.name}.{name}")


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


def _portfolio_securities() -> list[str]:
    return list(get_session().context.portfolio.positions)


def _order_from_any(value) -> Order | None:
    if value is None:
        return None
    if isinstance(value, Order):
        return value
    if not isinstance(value, dict):
        return None
    status = value.get("status", OrderStatus.open)
    if not isinstance(status, OrderStatus):
        status = OrderStatus.__members__.get(str(status).lower(), OrderStatus.open)
    return Order(
        security=value.get("security", ""),
        amount=int(value.get("amount", 0) or 0),
        value=float(value.get("value", 0.0) or 0.0),
        price=float(value.get("price", 0.0) or 0.0),
        filled=int(value.get("filled", value.get("filled_amount", 0)) or 0),
        status=status,
        filled_amount=int(value.get("filled_amount", value.get("filled", 0)) or 0),
        commission=float(value.get("commission", 0.0) or 0.0),
        avg_cost=float(value.get("avg_cost", 0.0) or 0.0),
        reason=value.get("reason"),
        is_buy=bool(value.get("is_buy", int(value.get("amount", 0) or 0) >= 0)),
        order_id=value.get("order_id") or value.get("client_order_id") or value.get("broker_order_id"),
        side=value.get("side", "long"),
        action=value.get("action", "open"),
    )


class _JoinQuantSeries(pd.Series):
    @property
    def _constructor(self):
        return _JoinQuantSeries

    @property
    def _constructor_expanddim(self):
        return _JoinQuantDataFrame

    def __getitem__(self, key):
        if isinstance(key, int):
            try:
                return super().__getitem__(key)
            except KeyError:
                if self.index.inferred_type in {"integer", "mixed-integer"}:
                    raise
                return self.iloc[key]
        return super().__getitem__(key)


class _JoinQuantDataFrame(pd.DataFrame):
    @property
    def _constructor(self):
        return _JoinQuantDataFrame

    @property
    def _constructor_sliced(self):
        return _JoinQuantSeries


def _jq_dataframe(value):
    if isinstance(value, pd.DataFrame) and not isinstance(value, _JoinQuantDataFrame):
        value = _JoinQuantDataFrame(value)
    return value


__all__ = [name for name in globals() if not name.startswith("_")]
