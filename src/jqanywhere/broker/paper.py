"""Paper broker implementation."""

from __future__ import annotations

from jqanywhere.broker.base import Broker
from jqanywhere.jqcompat.types import Context, Order, Position


class PaperBroker(Broker):
    def order_target_value(self, context: Context, security: str, value: float, **kwargs) -> Order | None:
        price = float(kwargs.get("price") or 1.0)
        target_value = max(float(value), 0.0)
        current = context.portfolio.positions.get(security)
        current_value = current.value if current else 0.0
        delta = target_value - current_value

        if delta > context.portfolio.available_cash:
            target_value = current_value + context.portfolio.available_cash
            delta = target_value - current_value

        context.portfolio.available_cash -= delta
        amount = int(target_value / price) if price > 0 else 0

        if target_value <= 0 or amount <= 0:
            context.portfolio.positions.pop(security, None)
            return Order(security=security, amount=0, value=0.0, price=price)

        context.portfolio.positions[security] = Position(
            security=security,
            total_amount=amount,
            closeable_amount=amount,
            price=price,
            avg_cost=price,
            value=target_value,
        )
        return Order(security=security, amount=amount, value=target_value, price=price)

    def order_target(self, context: Context, security: str, amount: int, **kwargs) -> Order | None:
        price = float(kwargs.get("price") or 1.0)
        return self.order_target_value(context, security, amount * price, **kwargs)

    def order(self, context: Context, security: str, amount: int, **kwargs) -> Order | None:
        price = float(kwargs.get("price") or 1.0)
        current = context.portfolio.positions.get(security)
        current_amount = current.total_amount if current else 0
        return self.order_target(context, security, current_amount + amount, **kwargs)
