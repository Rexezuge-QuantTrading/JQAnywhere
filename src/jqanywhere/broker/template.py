"""Template for real broker integrations."""

from __future__ import annotations

from jqanywhere.broker.base import Broker
from jqanywhere.jqcompat.types import Context, Order


class TemplateBroker(Broker):
    """Copy this class when integrating a live broker.

    Implement account sync, symbol translation, order submission, retry policy,
    and idempotency in your concrete broker adapter. Strategies continue to call
    JoinQuant-style functions such as order_target_value.
    """

    def order_target_value(self, context: Context, security: str, value: float, **kwargs) -> Order | None:
        raise NotImplementedError("Replace TemplateBroker with a real broker implementation")
