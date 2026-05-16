"""Broker interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod

from jqanywhere.jqcompat.types import Context, Order


class Broker(ABC):
    @abstractmethod
    def order_target_value(self, context: Context, security: str, value: float, **kwargs) -> Order | None:
        raise NotImplementedError

    def order(self, context: Context, security: str, amount: int, **kwargs) -> Order | None:
        raise NotImplementedError("JQAnywhere v0.1 only provides order via broker templates unless implemented by the selected broker")

    def order_target(self, context: Context, security: str, amount: int, **kwargs) -> Order | None:
        raise NotImplementedError("JQAnywhere v0.1 only provides order_target via broker templates unless implemented by the selected broker")

    def order_value(self, context: Context, security: str, value: float, **kwargs) -> Order | None:
        return self.order_target_value(context, security, value, **kwargs)
