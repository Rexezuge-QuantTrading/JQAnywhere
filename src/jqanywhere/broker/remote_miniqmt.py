"""Remote MiniQMT-agent broker implementation."""

from __future__ import annotations

import hashlib
from typing import Any

from jqanywhere.broker.base import Broker
from jqanywhere.jqcompat.types import Context, LimitOrderStyle, Order, Position


class RemoteMiniQmtBroker(Broker):
    """Broker adapter that sends orders to a separately deployed MiniQMT agent."""

    def __init__(
        self,
        client,
        account_id: str,
        account_type: str = "STOCK",
        strategy_name: str = "jqanywhere",
        enable_trading: bool = False,
    ):
        self.client = client
        self.account_id = account_id
        self.account_type = account_type
        self.strategy_name = strategy_name
        self.enable_trading = enable_trading

    def sync_portfolio(self, context: Context) -> None:
        response = self.client.get(f"/v1/accounts/{self.account_id}/portfolio", {"account_type": self.account_type})
        context.portfolio.available_cash = float(response.get("available_cash", response.get("cash", context.portfolio.available_cash)))
        positions = response.get("positions", [])
        if isinstance(positions, dict):
            positions = [{"security": security, **payload} for security, payload in positions.items()]
        context.portfolio.positions = {
            item["security"]: Position(
                security=item["security"],
                total_amount=int(item.get("total_amount", item.get("volume", 0))),
                closeable_amount=int(item.get("closeable_amount", item.get("can_use_volume", 0))),
                price=float(item.get("price", item.get("last_price", 0.0)) or 0.0),
                avg_cost=float(item.get("avg_cost", item.get("avg_price", 0.0)) or 0.0),
                value=float(item.get("value", item.get("market_value", 0.0)) or 0.0),
            )
            for item in positions
        }

    def order_target_value(self, context: Context, security: str, value: float, **kwargs) -> Order | None:
        return self._submit_order(context, "order_target_value", security, {"target_value": float(value)}, kwargs)

    def order_target(self, context: Context, security: str, amount: int, **kwargs) -> Order | None:
        return self._submit_order(context, "order_target", security, {"target_amount": int(amount)}, kwargs)

    def order(self, context: Context, security: str, amount: int, **kwargs) -> Order | None:
        return self._submit_order(context, "order", security, {"amount": int(amount)}, kwargs)

    def _submit_order(self, context: Context, method: str, security: str, order_payload: dict[str, Any], kwargs: dict[str, Any]) -> Order:
        if not self.enable_trading:
            raise RuntimeError("Remote MiniQMT trading is disabled; set broker.enable_trading = true after validating the agent")
        client_order_id, run_key, fingerprint = _client_order_id(context, self.strategy_name, method, security, order_payload)
        payload = {
            "account_id": self.account_id,
            "account_type": self.account_type,
            "client_order_id": client_order_id,
            "strategy_id": self.strategy_name,
            "method": method,
            "security": security,
            "style": _style_payload(kwargs.get("style")),
            "side": kwargs.get("side", "long"),
            "pindex": kwargs.get("pindex", 0),
            "close_today": kwargs.get("close_today", False),
            **order_payload,
        }
        response = self.client.post("/v1/orders", payload)
        order = _order_from_response(context, security, response)
        _record_order(context, order, response, payload, run_key, fingerprint)
        return order


def _style_payload(style) -> dict[str, Any]:
    if isinstance(style, LimitOrderStyle):
        return {"type": "limit", "price": style.price}
    price = getattr(style, "price", None)
    if price is not None:
        return {"type": "limit", "price": price}
    return {"type": "market"}


def _client_order_id(context: Context, strategy_name: str, method: str, security: str, payload: dict[str, Any]) -> tuple[str, str, str]:
    run_key = context.current_dt.replace(second=0, microsecond=0).isoformat()
    fingerprint = f"{method}:{security}:{sorted(payload.items())}"
    for item in context.order_history:
        if item.get("run_key") == run_key and item.get("fingerprint") == fingerprint and item.get("client_order_id"):
            return item["client_order_id"], run_key, fingerprint
    sequence = sum(1 for item in context.order_history if item.get("run_key") == run_key) + 1
    digest = hashlib.sha1(f"{strategy_name}:{run_key}:{sequence}:{fingerprint}".encode()).hexdigest()[:18]
    return f"jq{digest}", run_key, fingerprint


def _order_from_response(context: Context, security: str, response: dict[str, Any]) -> Order:
    status = str(response.get("status", "submitted"))
    amount = int(response.get("amount", response.get("filled_amount", 0)) or 0)
    price = float(response.get("price", 0.0) or 0.0)
    value = float(response.get("value", abs(amount) * price) or 0.0)
    filled_amount = int(response.get("filled_amount", amount if status in {"filled", "succeeded", "completed"} else 0) or 0)
    return Order(
        security=response.get("security", security),
        amount=amount,
        value=value,
        price=price,
        filled=filled_amount,
        status=status,
        filled_amount=filled_amount,
        commission=float(response.get("commission", 0.0) or 0.0),
        avg_cost=float(response.get("avg_cost", response.get("avg_price", price)) or 0.0),
        reason=response.get("reason"),
        add_time=context.current_dt,
    )


def _record_order(
    context: Context,
    order: Order,
    response: dict[str, Any],
    payload: dict[str, Any],
    run_key: str,
    fingerprint: str,
) -> None:
    context.order_history.append(
        {
            "security": order.security,
            "amount": order.amount,
            "value": order.value,
            "price": order.price,
            "filled": order.filled,
            "status": order.status,
            "filled_amount": order.filled_amount,
            "commission": order.commission,
            "reason": order.reason,
            "add_time": order.add_time.isoformat() if order.add_time is not None else None,
            "account_id": payload["account_id"],
            "method": payload["method"],
            "client_order_id": payload["client_order_id"],
            "broker_order_id": response.get("broker_order_id"),
            "run_key": run_key,
            "fingerprint": fingerprint,
        }
    )
