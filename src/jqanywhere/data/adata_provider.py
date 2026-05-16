"""Optional AData-backed market data provider."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from jqanywhere.data.base import MarketDataProvider
from jqanywhere.jqcompat.types import CurrentData


class LazyCurrentData(dict):
    def __init__(self, fetch_one):
        super().__init__()
        self._fetch_one = fetch_one

    def __missing__(self, security: str) -> CurrentData:
        value = self._fetch_one(security)
        self[security] = value
        return value


class ADataMarketDataProvider(MarketDataProvider):
    """AData-backed China market data adapter for JoinQuant-style APIs."""

    def __init__(self, strict_current_date: bool = False):
        try:
            import adata
        except ModuleNotFoundError as exc:  # pragma: no cover - exercised when optional dependency is absent.
            raise ModuleNotFoundError("adata is required when data.provider is 'adata'") from exc
        self.adata = adata
        self.strict_current_date = strict_current_date

    def attribute_history(self, security: str, count: int, unit: str, fields, skip_paused: bool, df: bool, fq: str | None):
        field_list = [fields] if isinstance(fields, str) else list(fields)
        raw = self._fetch_history(security, count, unit, fq)
        data = self._format_history(raw, unit, field_list, skip_paused)
        data = data.tail(count)
        return data if df else {field: data[field].to_numpy() for field in field_list}

    def get_current_data(self) -> dict[str, CurrentData]:
        return LazyCurrentData(self._fetch_current_data)

    def _fetch_history(self, security: str, count: int, unit: str, fq: str | None) -> pd.DataFrame:
        code = _security_code(security)
        end_dt, start_dt, k_type = _history_window(count, unit)
        adjust_type = {"pre": 1, "post": 2, None: 0}.get(fq, 1)
        buffer_days = (end_dt - start_dt).days

        for _attempt in range(2):
            try:
                if _is_etf(code):
                    if not unit.endswith("d"):
                        raise NotImplementedError("AData ETF minute history is not supported")
                    raw = self.adata.fund.market.get_market_etf(
                        fund_code=code,
                        k_type=1,
                        start_date=start_dt.strftime("%Y-%m-%d"),
                        end_date=end_dt.strftime("%Y-%m-%d"),
                    )
                elif unit.endswith("d"):
                    raw = self.adata.stock.market.get_market(
                        stock_code=code,
                        k_type=1,
                        start_date=start_dt.strftime("%Y-%m-%d"),
                        end_date=end_dt.strftime("%Y-%m-%d"),
                        adjust_type=adjust_type,
                    )
                else:
                    raw = self.adata.stock.market.get_market_min(stock_code=code)
            except Exception as exc:
                raise RuntimeError(f"Failed to fetch market history for {security}: {exc}") from exc

            if raw is not None and not raw.empty:
                result = raw.copy()
                time_col = "trade_time" if "trade_time" in result.columns else "trade_date"
                result.index = pd.to_datetime(result[time_col])
                result = result[result.index <= end_dt]
                if len(result) >= count:
                    return result

            buffer_days *= 2
            start_dt = end_dt - timedelta(days=buffer_days)

        raise ValueError(f"No market history found for {security}")

    def _format_history(self, raw: pd.DataFrame, unit: str, fields: list[str], skip_paused: bool) -> pd.DataFrame:
        field_map = {
            "open": "open",
            "close": "close",
            "high": "high",
            "low": "low",
            "volume": "volume",
            "money": "amount",
            "factor": "factor",
            "pre_close": "pre_close",
            "high_limit": "high_limit",
            "low_limit": "low_limit",
        }
        available = {field_map.get(field, field): field for field in fields if field_map.get(field, field) in raw.columns}
        data = raw[list(available.keys())].copy() if available else pd.DataFrame(index=raw.index)
        data = data.rename(columns=available)

        for col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")

        if "paused" in fields and "paused" not in data.columns:
            data["paused"] = (data["volume"] == 0).astype(int) if "volume" in data.columns else 0

        if not skip_paused and unit.endswith("d") and not data.empty:
            data = data.reindex(pd.bdate_range(start=data.index.min(), end=data.index.max())).ffill()
            if "volume" in data.columns and "paused" in data.columns:
                data.loc[data["paused"] == 1, "volume"] = 0.0
            if "money" in data.columns and "paused" in data.columns:
                data.loc[data["paused"] == 1, "money"] = 0.0
        elif skip_paused and "volume" in data.columns:
            data = data[data["volume"] > 0]

        for field in fields:
            if field not in data.columns:
                data[field] = np.nan
        return data[fields]

    def _fetch_current_data(self, security: str) -> CurrentData:
        code = _security_code(security)
        try:
            if _is_etf(code):
                raw = self.adata.fund.market.get_market_etf_current(fund_code=code)
            else:
                raw = self.adata.stock.market.get_market_current(stock_code=code)
        except Exception:
            return CurrentData(security=security, paused=True)

        if raw is None or raw.empty:
            return CurrentData(security=security, paused=True)

        row = raw.iloc[0]
        price = _row_get(row, "price")
        volume = _row_get(row, "volume", 0)
        trade_date = _row_get(row, "trade_date")
        paused = price is None or pd.isna(price) or volume is None or float(volume) == 0
        if self.strict_current_date and trade_date is not None:
            paused = paused or _parse_date(trade_date) != date.today()
        return CurrentData(security=security, paused=paused, last_price=None if price is None or pd.isna(price) else float(price))


def _security_code(security: str) -> str:
    return security.split(".", maxsplit=1)[0]


def _is_etf(code: str) -> bool:
    return code.startswith(("51", "15", "58", "56"))


def _history_window(count: int, unit: str) -> tuple[datetime, datetime, int]:
    now = datetime.now()
    if unit.endswith("d"):
        unit_val = int(unit[:-1])
        end_dt = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        buffer_days = int(count * unit_val * 1.5) + 30
        return end_dt, end_dt - timedelta(days=buffer_days), 1
    if unit.endswith("m"):
        k_type = int(unit[:-1])
        if k_type not in [1, 5, 15, 30, 60]:
            raise ValueError("unit must be one of '1m', '5m', '15m', '30m', or '60m'")
        end_dt = now.replace(second=0, microsecond=0) - timedelta(minutes=1)
        buffer_days = int(math.ceil(count / (240 / k_type)) * 1.5) + 15
        return end_dt, end_dt - timedelta(days=buffer_days), k_type
    raise ValueError("unit must use Xd or Xm format")


def _row_get(row: Any, key: str, default=None):
    value = row.get(key, default)
    return default if value is None else value


def _parse_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return datetime.strptime(value, "%Y-%m-%d").date()
    return None
