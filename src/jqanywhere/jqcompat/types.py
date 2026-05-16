"""JoinQuant-compatible data types used by the v0.1 API subset."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class OrderCost:
    open_tax: float = 0.0
    close_tax: float = 0.0
    open_commission: float = 0.0
    close_commission: float = 0.0
    close_today_commission: float = 0.0
    min_commission: float = 0.0


@dataclass
class FixedSlippage:
    value: float = 0.0


@dataclass
class PerTrade:
    buy_cost: float = 0.0
    sell_cost: float = 0.0
    min_cost: float = 0.0


class MarketOrderStyle:
    pass


@dataclass
class LimitOrderStyle:
    price: float


@dataclass
class Position:
    security: str
    total_amount: int = 0
    closeable_amount: int = 0
    price: float = 0.0
    avg_cost: float = 0.0
    value: float = 0.0


@dataclass
class Portfolio:
    starting_cash: float
    available_cash: float
    positions: dict[str, Position] = field(default_factory=dict)

    @property
    def positions_value(self) -> float:
        return sum(position.value for position in self.positions.values())

    @property
    def total_value(self) -> float:
        return self.available_cash + self.positions_value

    @property
    def portfolio_value(self) -> float:
        return self.total_value


@dataclass
class Context:
    portfolio: Portfolio
    current_dt: datetime
    previous_date: Any = None


@dataclass
class CurrentData:
    security: str
    paused: bool = False
    last_price: float | None = None


@dataclass
class Order:
    security: str
    amount: int
    value: float
    price: float
    filled: bool = True
