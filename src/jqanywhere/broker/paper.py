"""Event-driven paper-trading broker implementation."""

from __future__ import annotations

from datetime import date, datetime

from jqanywhere.broker.base import Broker
from jqanywhere.jqcompat.types import (
    Context,
    FixedSlippage,
    Order,
    OrderCost,
    OrderStatus,
    PerTrade,
    Position,
    PriceRelatedSlippage,
    StepRelatedSlippage,
)
from jqanywhere.runtime.state import get_session


class PaperBroker(Broker):
    def sync_portfolio(self, context: Context) -> None:
        for security, position in list(context.portfolio.positions.items()):
            if _position_last_trade_date(position) != context.current_dt.date():
                position.closeable_amount = position.total_amount
            price = _order_price(context, security, {})
            if price > 0:
                position.price = price
                position.value = position.total_amount * price

    def order_target_value(self, context: Context, security: str, value: float, **kwargs) -> Order | None:
        side = kwargs.get("side", "long")
        if side != "long":
            order = _rejected_order(context, security, 0, 0.0, _order_price(context, security, kwargs), "unsupported_side")
            _record_order(context, order)
            return order

        current_data = _current_data(security)
        price = _order_price(context, security, kwargs)
        if current_data is not None and current_data.paused:
            order = _rejected_order(context, security, 0, 0.0, price, "paused")
            _record_order(context, order)
            return None

        target_value = max(float(value), 0.0)
        current = context.portfolio.positions.get(security)
        current_amount = current.total_amount if current else 0
        target_amount = int(target_value / price) if price > 0 else 0
        delta_amount = target_amount - current_amount
        if delta_amount == 0:
            order = Order(
                security=security,
                amount=0,
                value=0.0,
                price=price,
                filled=0,
                filled_amount=0,
                add_time=context.current_dt,
                order_id=_next_order_id(context),
            )
            _record_order(context, order)
            return order

        execution_price = _execution_price(security, price, delta_amount)
        if _blocked_by_price_limit(current_data, execution_price, delta_amount):
            order = _rejected_order(context, security, delta_amount, 0.0, execution_price, "price_limit")
            _record_order(context, order)
            return None

        trade_value = abs(delta_amount) * execution_price
        commission = _commission(security, trade_value, delta_amount, kwargs)

        if delta_amount > 0:
            max_affordable = int(context.portfolio.available_cash / execution_price) if execution_price > 0 else 0
            while (
                max_affordable > 0
                and max_affordable * execution_price + _commission(security, max_affordable * execution_price, max_affordable, kwargs)
                > context.portfolio.available_cash
            ):
                max_affordable -= 1
            if delta_amount > max_affordable:
                delta_amount = max_affordable
                trade_value = delta_amount * execution_price
                commission = _commission(security, trade_value, delta_amount, kwargs)
            if delta_amount <= 0:
                order = _rejected_order(context, security, 0, 0.0, execution_price, "insufficient_cash")
                _record_order(context, order)
                return None
            target_amount = current_amount + delta_amount
            context.portfolio.available_cash -= trade_value + commission
            closeable_amount = current.closeable_amount if current else 0
        else:
            sell_amount = min(abs(delta_amount), current.closeable_amount if current else 0)
            if sell_amount <= 0:
                order = _rejected_order(context, security, delta_amount, 0.0, execution_price, "insufficient_position")
                _record_order(context, order)
                return None
            delta_amount = -sell_amount
            target_amount = current_amount - sell_amount
            trade_value = sell_amount * execution_price
            commission = _commission(security, trade_value, delta_amount, kwargs)
            context.portfolio.available_cash += trade_value - commission
            closeable_amount = max((current.closeable_amount if current else 0) - sell_amount, 0)

        if target_amount <= 0:
            context.portfolio.positions.pop(security, None)
        else:
            context.portfolio.positions[security] = Position(
                security=security,
                total_amount=target_amount,
                # Minimal China-market T+1 support: shares bought in the current
                # invocation day stay non-closeable until a later trading-day run.
                closeable_amount=closeable_amount,
                price=execution_price,
                avg_cost=_avg_cost(current, current_amount, delta_amount, execution_price),
                value=target_amount * execution_price,
                last_trade_date=context.current_dt.date().isoformat(),
            )

        order = Order(
            security=security,
            amount=abs(delta_amount),
            value=trade_value,
            price=execution_price,
            filled=abs(delta_amount),
            status=OrderStatus.held,
            filled_amount=abs(delta_amount),
            commission=commission,
            avg_cost=current.avg_cost if current is not None else execution_price,
            add_time=context.current_dt,
            order_id=_next_order_id(context),
            is_buy=delta_amount > 0,
            side=kwargs.get("side", "long"),
            action="open" if delta_amount > 0 else "close",
        )
        _record_order(context, order)
        return order

    def order_target(self, context: Context, security: str, amount: int, **kwargs) -> Order | None:
        price = _order_price(context, security, kwargs)
        return self.order_target_value(context, security, amount * price, **kwargs)

    def order(self, context: Context, security: str, amount: int, **kwargs) -> Order | None:
        current = context.portfolio.positions.get(security)
        current_amount = current.total_amount if current else 0
        if amount < 0 and (current is None or current.closeable_amount <= 0):
            price = _order_price(context, security, kwargs)
            order = _rejected_order(context, security, amount, 0.0, price, "insufficient_position")
            _record_order(context, order)
            return None
        return self.order_target(context, security, current_amount + amount, **kwargs)


def _order_price(context: Context, security: str, kwargs) -> float:
    style = kwargs.get("style")
    explicit = kwargs.get("price") or getattr(style, "price", None)
    if explicit:
        return float(explicit)
    current_data = _current_data(security)
    if current_data is not None and current_data.last_price:
        return float(current_data.last_price)
    try:
        history = get_session().data.attribute_history(security, 1, "1d", ["close"], True, True, "pre")
    except Exception:
        return 1.0
    if len(history) and "close" in history:
        return float(history["close"].iloc[-1])
    return 1.0


def _current_data(security: str):
    try:
        return get_session().data.get_current_data()[security]
    except Exception:
        return None


def _execution_price(security: str, price: float, amount: int) -> float:
    slippage = _session_value("slippages", "slippage", security)
    if isinstance(slippage, FixedSlippage):
        return max(price + slippage.value if amount > 0 else price - slippage.value, 0.0)
    if isinstance(slippage, PriceRelatedSlippage):
        delta = price * slippage.value
        return max(price + delta if amount > 0 else price - delta, 0.0)
    if isinstance(slippage, StepRelatedSlippage):
        return max(price + slippage.value if amount > 0 else price - slippage.value, 0.0)
    return price


def _commission(security: str, value: float, amount: int, kwargs) -> float:
    cost = _session_value("order_costs", "order_cost", security)
    if isinstance(cost, OrderCost):
        close_commission = cost.close_today_commission if amount < 0 and kwargs.get("close_today") else cost.close_commission
        rate = cost.open_commission + cost.open_tax if amount > 0 else close_commission + cost.close_tax
        return max(value * rate, cost.min_commission if value else 0.0)
    if isinstance(cost, PerTrade):
        rate = cost.buy_cost if amount > 0 else cost.sell_cost
        return max(value * rate, cost.min_cost if value else 0.0)
    return 0.0


def _blocked_by_price_limit(current_data, price: float, amount: int) -> bool:
    if current_data is None:
        return False
    if amount > 0 and current_data.high_limit is not None and price >= current_data.high_limit:
        return True
    return amount < 0 and current_data.low_limit is not None and price <= current_data.low_limit


def _position_last_trade_date(position: Position) -> date | None:
    value = position.last_trade_date
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value).date()
    return None


def _avg_cost(current: Position | None, current_amount: int, delta_amount: int, price: float) -> float:
    if delta_amount <= 0 or current is None or current_amount <= 0:
        return current.avg_cost if current is not None else price
    return ((current.avg_cost * current_amount) + (price * delta_amount)) / (current_amount + delta_amount)


def _rejected_order(context: Context, security: str, amount: int, value: float, price: float, reason: str) -> Order:
    return Order(
        security=security,
        amount=amount,
        value=value,
        price=price,
        filled=0,
        status=OrderStatus.rejected,
        filled_amount=0,
        reason=reason,
        add_time=context.current_dt,
        order_id=_next_order_id(context),
        is_buy=amount > 0,
        action="open" if amount > 0 else "close",
    )


def _next_order_id(context: Context) -> str:
    return f"paper-{len(context.order_history) + 1}"


def _session_value(mapping_name: str, fallback_name: str, security: str):
    session = get_session()
    mapping = getattr(session, mapping_name)
    asset_type = _asset_type(security)
    return mapping.get(security) or mapping.get(asset_type) or mapping.get("default") or getattr(session, fallback_name)


def _asset_type(security: str) -> str:
    code = security.split(".", maxsplit=1)[0]
    if code.startswith(("15", "16", "18", "50", "51", "56", "58")):
        return "fund"
    return "stock"


def _record_order(context: Context, order: Order) -> None:
    context.order_history.append(
        {
            "security": order.security,
            "amount": order.amount,
            "value": order.value,
            "price": order.price,
            "filled": order.filled,
            "status": order.status.name if isinstance(order.status, OrderStatus) else str(order.status),
            "filled_amount": order.filled_amount if order.filled_amount is not None else order.amount,
            "commission": order.commission,
            "avg_cost": order.avg_cost,
            "reason": order.reason,
            "add_time": order.add_time.isoformat() if order.add_time is not None else None,
            "order_id": order.order_id,
            "is_buy": order.is_buy,
            "side": order.side,
            "action": order.action,
        }
    )
