"""Market data provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from jqanywhere.jqcompat.types import CurrentData

try:
    import pandas as pd
except ModuleNotFoundError:  # pragma: no cover - dependency is installed in normal package usage.
    pd = None


class MarketDataProvider(ABC):
    @abstractmethod
    def attribute_history(self, security: str, count: int, unit: str, fields, skip_paused: bool, df: bool, fq: str | None):
        raise NotImplementedError

    @abstractmethod
    def get_current_data(self) -> dict[str, CurrentData]:
        raise NotImplementedError

    def get_price(self, security, *args, **kwargs):
        raise NotImplementedError("JQAnywhere v0.1 does not implement get_price")

    def get_index_stocks(self, index_symbol: str, date=None) -> list[str]:
        raise NotImplementedError("JQAnywhere v0.1 does not implement get_index_stocks")


class EmptyMarketDataProvider(MarketDataProvider):
    def attribute_history(self, security: str, count: int, unit: str, fields, skip_paused: bool, df: bool, fq: str | None):
        if pd is None:
            raise ModuleNotFoundError("pandas is required for attribute_history")
        field_list = [fields] if isinstance(fields, str) else list(fields)
        data = pd.DataFrame({field: [] for field in field_list})
        return data if df else {field: data[field].to_numpy() for field in field_list}

    def get_current_data(self) -> dict[str, CurrentData]:
        return {}


class StaticMarketDataProvider(MarketDataProvider):
    def __init__(self, history: dict[str, pd.DataFrame] | None = None, current: Iterable[str] | None = None):
        self.history = history or {}
        self.current = {code: CurrentData(code, paused=False) for code in (current or [])}

    def attribute_history(self, security: str, count: int, unit: str, fields, skip_paused: bool, df: bool, fq: str | None):
        if pd is None:
            raise ModuleNotFoundError("pandas is required for attribute_history")
        field_list = [fields] if isinstance(fields, str) else list(fields)
        data = self.history.get(security, pd.DataFrame(columns=field_list)).tail(count)
        data = data.reindex(columns=field_list)
        return data if df else {field: data[field].to_numpy() for field in field_list}

    def get_current_data(self) -> dict[str, CurrentData]:
        return self.current
