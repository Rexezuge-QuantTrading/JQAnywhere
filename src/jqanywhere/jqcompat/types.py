"""JoinQuant-compatible data types used by the public API subset."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from jqanywhere import __version__
from jqanywhere.jqcompat.logging import BufferedLogger


def _unsupported(name: str):
    raise NotImplementedError(f"JQAnywhere v{__version__} does not support {name}")


class Logger(BufferedLogger):
    pass


@dataclass
class OrderCost:
    open_tax: float = 0.0
    close_tax: float = 0.0
    open_commission: float = 0.0
    close_commission: float = 0.0
    close_today_commission: float = 0.0
    min_commission: float = 0.0
    type: str | None = None
    ref: str | None = None


class BaseSlippage:
    pass


@dataclass
class FixedSlippage(BaseSlippage):
    value: float = 0.0


@dataclass
class PriceRelatedSlippage(BaseSlippage):
    value: float = 0.0


@dataclass
class StepRelatedSlippage(BaseSlippage):
    value: float = 0.0


@dataclass
class PerTrade:
    buy_cost: float = 0.0
    sell_cost: float = 0.0
    min_cost: float = 0.0


class OrderStyle:
    pass


class MarketOrderStyle(OrderStyle):
    def __init__(self, limit_price: float | None = None):
        self.limit_price = limit_price


class LimitOrderStyle(OrderStyle):
    def __init__(self, limit_price: float | None = None):
        self.limit_price = limit_price
        self.price = limit_price


class StopMarketOrderStyle(OrderStyle):
    def __init__(self, mode: str, stop_price: float) -> None:
        del mode, stop_price
        _unsupported("StopMarketOrderStyle")


class StopLimitOrderStyle(OrderStyle):
    def __init__(self, mode: str, stop_price: float, limit_price: float) -> None:
        del mode, stop_price, limit_price
        _unsupported("StopLimitOrderStyle")


@dataclass
class Position:
    security: str
    total_amount: int = 0
    closeable_amount: int = 0
    price: float = 0.0
    avg_cost: float = 0.0
    acc_avg_cost: float = 0.0
    hold_cost: float = 0.0
    value: float = 0.0
    init_time: Any = None
    transact_time: Any = None
    locked_amount: float = 0.0
    today_amount: float = 0.0
    side: str = "long"
    last_trade_date: Any = None
    pindex: int = 0


@dataclass
class SubPortfolioConfig:
    cash: float
    type: str = "stock"


@dataclass
class RunParams:
    type: str = "sim_trade"
    start_date: Any = None
    end_date: Any = None
    frequency: str = "minute"


@dataclass
class Portfolio:
    starting_cash: float
    available_cash: float
    positions: dict[str, Position] = field(default_factory=dict)
    type: str = "stock"

    @property
    def inout_cash(self) -> float:
        return self.starting_cash

    @property
    def transferable_cash(self) -> float:
        return self.available_cash

    @property
    def locked_cash(self) -> float:
        return 0.0

    @property
    def margin(self) -> float:
        return 0.0

    @property
    def long_positions(self) -> dict[str, Position]:
        return self.positions

    @property
    def short_positions(self) -> dict[str, Position]:
        return {}

    @property
    def positions_value(self) -> float:
        return sum(position.value for position in self.positions.values())

    @property
    def total_value(self) -> float:
        return self.available_cash + self.positions_value

    @property
    def portfolio_value(self) -> float:
        return self.total_value

    @property
    def returns(self) -> float:
        if self.starting_cash == 0:
            return 0.0
        return self.total_value / self.starting_cash - 1

    @property
    def total_liability(self) -> float:
        return 0.0

    @property
    def net_value(self) -> float:
        return self.total_value

    @property
    def cash_liability(self) -> float:
        return 0.0

    @property
    def sec_liability(self) -> float:
        return 0.0

    @property
    def interest(self) -> float:
        return 0.0

    @property
    def maintenance_margin_rate(self) -> float:
        return 0.0

    @property
    def available_margin(self) -> float:
        return 0.0

    def is_dangerous(self, margin_rate: float) -> bool:
        del margin_rate
        return False


@dataclass
class Context:
    portfolio: Portfolio
    current_dt: datetime
    previous_date: Any = None
    universe: list[str] = field(default_factory=list)
    order_history: list[Any] = field(default_factory=list)
    run_params: RunParams = field(default_factory=RunParams)
    subportfolios: list[Portfolio] = field(default_factory=list)


@dataclass
class CurrentData:
    security: str
    paused: bool = False
    last_price: float | None = None
    high: float | None = None
    low: float | None = None
    high_limit: float | None = None
    low_limit: float | None = None
    is_st: bool | None = None
    day_open: float | None = None
    pre_close: float | None = None
    volume: float | None = None
    money: float | None = None
    avg_price: float | None = None
    name: str | None = None
    industry_code: str | None = None


@dataclass
class SecurityInfo:
    code: str
    display_name: str | None = None
    name: str | None = None
    start_date: Any = None
    end_date: Any = None
    type: str | None = None
    parent: str | None = None


CurrentDataObject = CurrentData
SecurityInfoObject = SecurityInfo
SubPortfolio = Portfolio


@dataclass
class SecurityUnitData:
    open: float = 0.0
    close: float = 0.0
    low: float = 0.0
    high: float = 0.0
    volume: float = 0.0
    money: float = 0.0
    factor: Any = None
    high_limit: float = 0.0
    low_limit: float = 0.0
    avg: float = 0.0
    pre_close: float = 0.0
    paused: bool = False


@dataclass
class TickObject:
    code: str = ""
    datetime: datetime | None = None
    current: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    volume: int = 0
    money: float = 0.0
    position: int = 0
    b1_v: float = 0.0
    b2_v: float = 0.0
    b3_v: float = 0.0
    b4_v: float = 0.0
    b5_v: float = 0.0
    b1_p: float = 0.0
    b2_p: float = 0.0
    b3_p: float = 0.0
    b4_p: float = 0.0
    b5_p: float = 0.0
    a1_v: float = 0.0
    a2_v: float = 0.0
    a3_v: float = 0.0
    a4_v: float = 0.0
    a5_v: float = 0.0
    a1_p: float = 0.0
    a2_p: float = 0.0
    a3_p: float = 0.0
    a4_p: float = 0.0
    a5_p: float = 0.0


@dataclass
class Trade:
    time: datetime | None = None
    security: str = ""
    amount: float = 0.0
    price: float = 0.0
    trade_id: str = ""
    order_id: str = ""


@dataclass
class DividendsEvent:
    name: str = "dividends"
    pindex: int = 0
    security: str = ""
    side: str = "long"
    dividends: list[dict] = field(default_factory=list)


@dataclass
class ForcedLiquidationEvent:
    name: str = "forced_liquidation"
    pindex: int = 0
    security: str = ""
    side: str = "long"
    amount: int = 0


class Factor:
    def __init__(self) -> None:
        self.dependencies = []
        self.max_window = None
        self.name = ""
        self.universe = ""

    def calc(self, data):
        del data
        _unsupported("custom factor calculation")


class OptimizeFunction:
    pass


class ConstraintFunction:
    pass


class BoundFunction:
    pass


class _UnsupportedOptimizerInput:
    _jq_name = "portfolio optimizer input"

    def __init__(self, *args, **kwargs) -> None:
        del args, kwargs
        _unsupported(self._jq_name)


class MinVariance(_UnsupportedOptimizerInput, OptimizeFunction):
    _jq_name = "MinVariance"


class MaxProfit(_UnsupportedOptimizerInput, OptimizeFunction):
    _jq_name = "MaxProfit"


class MaxSharpeRatio(_UnsupportedOptimizerInput, OptimizeFunction):
    _jq_name = "MaxSharpeRatio"


class MinTrackingError(_UnsupportedOptimizerInput, OptimizeFunction):
    _jq_name = "MinTrackingError"


class RiskParity(_UnsupportedOptimizerInput, OptimizeFunction):
    _jq_name = "RiskParity"


class MaxScore(_UnsupportedOptimizerInput, OptimizeFunction):
    _jq_name = "MaxScore"


class MinScore(_UnsupportedOptimizerInput, OptimizeFunction):
    _jq_name = "MinScore"


class MaxFactorValue(_UnsupportedOptimizerInput, OptimizeFunction):
    _jq_name = "MaxFactorValue"


class MinFactorValue(_UnsupportedOptimizerInput, OptimizeFunction):
    _jq_name = "MinFactorValue"


class WeightConstraint(_UnsupportedOptimizerInput, ConstraintFunction):
    _jq_name = "WeightConstraint"


class WeightEqualConstraint(_UnsupportedOptimizerInput, ConstraintFunction):
    _jq_name = "WeightEqualConstraint"


class AnnualStdConstraint(_UnsupportedOptimizerInput, ConstraintFunction):
    _jq_name = "AnnualStdConstraint"


class AnnualProfitConstraint(_UnsupportedOptimizerInput, ConstraintFunction):
    _jq_name = "AnnualProfitConstraint"


class IndustryConstraint(_UnsupportedOptimizerInput, ConstraintFunction):
    _jq_name = "IndustryConstraint"


class IndustriesConstraint(_UnsupportedOptimizerInput, ConstraintFunction):
    _jq_name = "IndustriesConstraint"


class MarketConstraint(_UnsupportedOptimizerInput, ConstraintFunction):
    _jq_name = "MarketConstraint"


class ExposureConstraint(_UnsupportedOptimizerInput, ConstraintFunction):
    _jq_name = "ExposureConstraint"


class BarraConstraint(_UnsupportedOptimizerInput, ConstraintFunction):
    _jq_name = "BarraConstraint"


class IndustryDeviationConstraint(_UnsupportedOptimizerInput, ConstraintFunction):
    _jq_name = "IndustryDeviationConstraint"


class IndustriesDeviationConstraint(_UnsupportedOptimizerInput, ConstraintFunction):
    _jq_name = "IndustriesDeviationConstraint"


class TrackingErrorConstraint(_UnsupportedOptimizerInput, ConstraintFunction):
    _jq_name = "TrackingErrorConstraint"


class TurnoverConstraint(_UnsupportedOptimizerInput, ConstraintFunction):
    _jq_name = "TurnoverConstraint"


class RatioConstraint(_UnsupportedOptimizerInput, ConstraintFunction):
    _jq_name = "RatioConstraint"


class MaxDrawdownConstraint(_UnsupportedOptimizerInput, ConstraintFunction):
    _jq_name = "MaxDrawdownConstraint"


class Bound(_UnsupportedOptimizerInput, BoundFunction):
    _jq_name = "Bound"


class IndustryBound(_UnsupportedOptimizerInput, BoundFunction):
    _jq_name = "IndustryBound"


class LiquidityBound(_UnsupportedOptimizerInput, BoundFunction):
    _jq_name = "LiquidityBound"


class CapBound(_UnsupportedOptimizerInput, BoundFunction):
    _jq_name = "CapBound"


class OrderStatus(Enum):
    new = 8
    open = 0
    filled = 1
    canceled = 2
    rejected = 3
    held = 4


@dataclass
class Order:
    security: str
    amount: int
    value: float
    price: float
    filled: int = 0
    status: OrderStatus = OrderStatus.held
    filled_amount: int | None = None
    commission: float = 0.0
    avg_cost: float = 0.0
    reason: str | None = None
    add_time: datetime | None = None
    is_buy: bool = True
    order_id: str | None = None
    side: str = "long"
    action: str = "open"
    pindex: int = 0
