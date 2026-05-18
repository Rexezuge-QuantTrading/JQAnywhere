"""Optional AData-backed market data provider."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from jqanywhere.data.base import MarketDataProvider, _filter_trade_days
from jqanywhere.jqcompat.types import CurrentData, SecurityInfo


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
        _patch_adata_cookie_when_mini_racer_is_unavailable(adata)
        self.adata = adata
        self.strict_current_date = strict_current_date

    def attribute_history(self, security: str, count: int, unit: str, fields, skip_paused: bool, df: bool, fq: str | None):
        field_list = _field_list(fields)
        unit_value, unit_kind = _parse_unit(unit)
        _validate_count(count)
        _validate_fq(fq)
        _validate_fields(field_list, unit_value)
        end_dt = _history_end(unit_kind)
        raw = self._fetch_history(security, count, unit_value, unit_kind, fq, end_dt=end_dt)
        data = self._format_history(raw, field_list, skip_paused, fill_paused=True)
        data = _resample_bars(data, unit_value, unit_kind, field_list).tail(count)
        return data if df else {field: data[field].to_numpy() for field in field_list}

    def get_current_data(self) -> dict[str, CurrentData]:
        return LazyCurrentData(self._fetch_current_data)

    def get_trade_days(self, start_date=None, end_date=None, count=None) -> list[date]:
        return _filter_trade_days(self.get_all_trade_days(), start_date, end_date, count)

    def get_all_trade_days(self) -> list[date]:
        return _calendar_dates(self._fetch_trade_calendar())

    def get_price(
        self,
        security,
        start_date=None,
        end_date=None,
        frequency="daily",
        fields=None,
        skip_paused=False,
        fq="pre",
        count=None,
        panel=True,
        fill_paused=True,
    ):
        securities = [security] if isinstance(security, str) else list(security)
        if not securities:
            raise ValueError("security must not be empty")
        if count is not None and start_date is not None:
            raise ValueError("count and start_date are mutually exclusive")
        if skip_paused and len(securities) > 1 and panel:
            raise ValueError("skip_paused=True for multiple securities requires panel=False")

        field_list = _field_list(fields or _STANDARD_FIELDS)
        unit_value, unit_kind = _normalize_frequency(frequency)
        _validate_fq(fq)
        _validate_fields(field_list, unit_value)
        end_dt = _coerce_end_date(end_date, unit_kind)
        if count is None and start_date is None:
            raise ValueError("get_price requires count or start_date for AData-backed requests")
        if count is not None:
            _validate_count(count)
        start_dt = _coerce_start_date(start_date, unit_kind) if start_date is not None else None

        frames = {}
        for code in securities:
            fetch_count = count if count is not None else _estimated_count(start_dt, end_dt, unit_value, unit_kind)
            raw = self._fetch_history(code, fetch_count, unit_value, unit_kind, fq, end_dt=end_dt, start_dt=start_dt)
            frame = self._format_history(raw, field_list, skip_paused, fill_paused)
            frame = _resample_bars(frame, unit_value, unit_kind, field_list)
            if start_dt is not None:
                frame = frame[frame.index >= start_dt]
            frame = frame[frame.index <= end_dt]
            if count is not None:
                frame = frame.tail(count)
            frames[code] = frame

        if len(securities) == 1:
            return frames[securities[0]]
        if panel:
            return {field: pd.concat({code: frames[code][field] for code in securities}, axis=1) for field in field_list}
        return pd.concat(frames, names=["security", "datetime"])

    def get_index_stocks(self, index_symbol: str, date=None) -> list[str]:
        code = _security_code(index_symbol)
        if date is not None:
            _coerce_date(date)
        candidates = [
            (getattr(getattr(self.adata, "stock", None), "info", None), "index_constituent"),
            (getattr(getattr(self.adata, "stock", None), "info", None), "get_index_stocks"),
            (getattr(getattr(self.adata, "stock", None), "info", None), "get_index_stock_cons"),
            (getattr(getattr(self.adata, "stock", None), "market", None), "get_index_stocks"),
        ]
        for owner, name in candidates:
            method = getattr(owner, name, None)
            if method is None:
                continue
            raw = method(index_code=code)
            if raw is None:
                return []
            if isinstance(raw, pd.DataFrame):
                for column in ("stock_code", "code", "constituent_code"):
                    if column in raw.columns:
                        return [_jq_code(value) for value in raw[column].dropna().astype(str).tolist()]
                return []
            return [_jq_code(value) for value in raw]
        raise NotImplementedError("Installed adata package does not expose index constituent data")

    def get_all_securities(self, types=None, date=None):
        if date is not None:
            _coerce_date(date)
        security_types = _security_types(types)
        frames = []
        for security_type in security_types:
            if security_type == "stock":
                frames.append(self._all_stock_securities())
            elif security_type in {"fund", "etf"}:
                frames.append(self._all_etf_securities())
            elif security_type == "index":
                frames.append(self._all_index_securities())
            elif security_type in {"bond", "cbond"}:
                frames.append(self._all_bond_securities())
            else:
                raise NotImplementedError(f"AData security type is not supported: {security_type}")
        if not frames:
            return pd.DataFrame(columns=["display_name", "name", "start_date", "end_date", "type"])
        return pd.concat(frames).sort_index()

    def get_security_info(self, code: str) -> SecurityInfo:
        security_type = _infer_security_type(code)
        search_types = [security_type] if security_type else ["stock", "fund", "index", "bond"]
        securities = self.get_all_securities(search_types)
        jq_code = _jq_code(code)
        if jq_code not in securities.index:
            raise ValueError(f"Security not found: {code}")
        row = securities.loc[jq_code]
        return SecurityInfo(
            code=jq_code,
            display_name=_none_if_nan(row.get("display_name")),
            name=_none_if_nan(row.get("name")),
            start_date=_none_if_nan(row.get("start_date")),
            end_date=_none_if_nan(row.get("end_date")),
            type=_none_if_nan(row.get("type")),
        )

    def _fetch_trade_calendar(self) -> pd.DataFrame:
        stock_info = getattr(getattr(self.adata, "stock", None), "info", None)
        method = getattr(stock_info, "trade_calendar", None)
        if method is None:
            raise NotImplementedError("Installed adata package does not expose trade calendar data")
        try:
            return method()
        except TypeError:
            frames = []
            for year in range(1990, date.today().year + 1):
                try:
                    frames.append(method(year=year))
                except TypeError:
                    frames.append(method(year))
            return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def _all_stock_securities(self) -> pd.DataFrame:
        raw = self.adata.stock.info.all_code()
        data = pd.DataFrame(index=[_jq_stock_code(row.stock_code, getattr(row, "exchange", None)) for row in raw.itertuples()])
        data["display_name"] = raw.get("short_name", pd.Series(index=raw.index, dtype=object)).to_list()
        data["name"] = data["display_name"]
        data["start_date"] = raw.get("list_date", pd.Series(index=raw.index, dtype=object)).to_list()
        data["end_date"] = None
        data["type"] = "stock"
        return data

    def _all_etf_securities(self) -> pd.DataFrame:
        raw = self.adata.fund.info.all_etf_exchange_traded_info()
        data = pd.DataFrame(index=[_jq_code(value) for value in raw["fund_code"].astype(str)])
        data["display_name"] = raw.get("short_name", pd.Series(index=raw.index, dtype=object)).to_list()
        data["name"] = data["display_name"]
        data["start_date"] = None
        data["end_date"] = None
        data["type"] = "fund"
        return data

    def _all_index_securities(self) -> pd.DataFrame:
        raw = self.adata.stock.info.all_index_code()
        data = pd.DataFrame(index=[_jq_index_code(value) for value in raw["index_code"].astype(str)])
        data["display_name"] = raw.get("name", pd.Series(index=raw.index, dtype=object)).to_list()
        data["name"] = data["display_name"]
        data["start_date"] = None
        data["end_date"] = None
        data["type"] = "index"
        return data

    def _all_bond_securities(self) -> pd.DataFrame:
        raw = self.adata.bond.info.all_convert_code()
        data = pd.DataFrame(index=[_jq_code(value) for value in raw["bond_code"].astype(str)])
        data["display_name"] = raw.get("bond_name", pd.Series(index=raw.index, dtype=object)).to_list()
        data["name"] = data["display_name"]
        data["start_date"] = raw.get("listing_date", pd.Series(index=raw.index, dtype=object)).to_list()
        data["end_date"] = raw.get("expire_date", pd.Series(index=raw.index, dtype=object)).to_list()
        data["type"] = "bond"
        return data

    def _fetch_history(
        self,
        security: str,
        count: int,
        unit_value: int,
        unit_kind: str,
        fq: str | None,
        *,
        end_dt: datetime,
        start_dt: datetime | None = None,
    ) -> pd.DataFrame:
        code = _security_code(security)
        explicit_start = start_dt is not None
        start_dt = start_dt or _history_start(count, unit_value, unit_kind, end_dt)
        adjust_type = {"pre": 1, "post": 2, None: 0}.get(fq, 1)
        buffer_days = max((end_dt - start_dt).days, 1)

        for _attempt in range(2):
            try:
                if _is_etf(code):
                    if unit_kind == "m":
                        raw = self.adata.fund.market.get_market_etf_min(fund_code=code)
                    else:
                        raw = self.adata.fund.market.get_market_etf(
                            fund_code=code,
                            k_type=1,
                            start_date=start_dt.strftime("%Y-%m-%d"),
                            end_date=end_dt.strftime("%Y-%m-%d"),
                        )
                elif _is_index_security(security):
                    if unit_kind == "m":
                        raw = self.adata.stock.market.get_market_index_min(index_code=code)
                    else:
                        raw = self.adata.stock.market.get_market_index(
                            index_code=code,
                            k_type=1,
                            start_date=start_dt.strftime("%Y-%m-%d"),
                        )
                elif unit_kind == "d":
                    raw = self.adata.stock.market.get_market(
                        stock_code=code,
                        k_type=1,
                        start_date=start_dt.strftime("%Y-%m-%d"),
                        end_date=end_dt.strftime("%Y-%m-%d"),
                        adjust_type=adjust_type,
                    )
                else:
                    if explicit_start and start_dt.date() != end_dt.date():
                        raise NotImplementedError("AData stock minute history only supports the latest trading day")
                    raw = self.adata.stock.market.get_market_min(stock_code=code)
            except NotImplementedError:
                raise
            except Exception as exc:
                raise RuntimeError(f"Failed to fetch market history for {security}: {exc}") from exc

            if raw is not None and not raw.empty:
                result = raw.copy()
                time_col = "trade_time" if "trade_time" in result.columns else "trade_date"
                result.index = pd.to_datetime(result[time_col])
                result = result.sort_index()
                result = result[result.index >= start_dt]
                result = result[result.index <= end_dt]
                if explicit_start or len(result) >= count:
                    return result

            buffer_days *= 2
            start_dt = end_dt - timedelta(days=buffer_days)

        raise ValueError(f"No market history found for {security}")

    def _format_history(self, raw: pd.DataFrame, fields: list[str], skip_paused: bool, fill_paused: bool) -> pd.DataFrame:
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
            "avg": "avg",
            "open_interest": "open_interest",
        }
        if "close" in fields and "close" not in raw.columns and "price" in raw.columns:
            field_map["close"] = "price"
        if "avg" in fields and "avg" not in raw.columns and "avg_price" in raw.columns:
            field_map["avg"] = "avg_price"
        available = {field_map.get(field, field): field for field in fields if field_map.get(field, field) in raw.columns}
        data = raw[list(available.keys())].copy() if available else pd.DataFrame(index=raw.index)
        data = data.rename(columns=available)

        for col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")

        pause_series = None
        if "volume" in data.columns:
            pause_series = data["volume"] == 0
        elif "volume" in raw.columns:
            pause_series = pd.to_numeric(raw["volume"], errors="coerce") == 0
        if "paused" in fields and "paused" not in data.columns:
            data["paused"] = pause_series.astype(int) if pause_series is not None else 0

        if skip_paused and "volume" in data.columns:
            data = data[data["volume"] > 0]
        elif skip_paused and "paused" in data.columns:
            data = data[data["paused"] == 0]
        elif fill_paused and not data.empty:
            price_fields = [
                field for field in ("open", "close", "high", "low", "avg", "pre_close", "high_limit", "low_limit") if field in data
            ]
            if price_fields:
                data.loc[:, price_fields] = data.loc[:, price_fields].ffill()
            for field in ("volume", "money"):
                if field in data and pause_series is not None:
                    data.loc[pause_series, field] = 0.0

        for field in fields:
            if field not in data.columns:
                data[field] = np.nan
        return data[fields]

    def _fetch_current_data(self, security: str) -> CurrentData:
        code = _security_code(security)
        try:
            if _is_etf(code):
                raw = self.adata.fund.market.get_market_etf_current(fund_code=code)
            elif _is_index_security(security):
                raw = self.adata.stock.market.get_market_index_current(index_code=code)
            else:
                raw = self.adata.stock.market.list_market_current(code_list=[code])
        except Exception:
            return CurrentData(security=security, paused=True)

        if raw is None or raw.empty:
            return CurrentData(security=security, paused=True)

        row = raw.iloc[0]
        price = _first_row_value(row, "price", "last_price", "close")
        volume = _row_get(row, "volume", 0)
        trade_date = _row_get(row, "trade_date")
        paused = price is None or pd.isna(price) or volume is None or float(volume) == 0
        if self.strict_current_date and trade_date is not None:
            paused = paused or _parse_date(trade_date) != date.today()
        return CurrentData(
            security=security,
            paused=paused,
            last_price=_float_or_none(price),
            high_limit=_float_or_none(_row_get(row, "high_limit")),
            low_limit=_float_or_none(_row_get(row, "low_limit")),
            is_st=_bool_or_none(_first_row_value(row, "is_st", "st")),
            day_open=_float_or_none(_first_row_value(row, "day_open", "open")),
            name=_first_row_value(row, "name", "short_name"),
            industry_code=_row_get(row, "industry_code"),
        )


_STANDARD_FIELDS = ["open", "close", "high", "low", "volume", "money"]
_MULTI_PERIOD_FIELDS = set(_STANDARD_FIELDS)


def _security_code(security: str) -> str:
    return security.split(".", maxsplit=1)[0]


def _patch_adata_cookie_when_mini_racer_is_unavailable(adata_module: Any) -> None:
    try:
        from py_mini_racer import py_mini_racer
    except Exception:
        _patch_adata_static_ths_cookie(adata_module)
        return

    extension_path = getattr(py_mini_racer, "EXTENSION_PATH", None)
    if extension_path is not None and not Path(extension_path).exists():
        _patch_adata_static_ths_cookie(adata_module)
        return

    try:
        py_mini_racer.MiniRacer()
    except Exception:
        _patch_adata_static_ths_cookie(adata_module)


def _patch_adata_static_ths_cookie(adata_module: Any) -> None:
    try:
        from adata.common.headers import ths_headers
        from adata.common.utils import cookie
    except Exception:
        return

    text_headers = getattr(ths_headers, "text_headers", {})
    header_cookie = text_headers.get("Cookie", "")
    v_cookie = next((part.strip() for part in header_cookie.split(";") if part.strip().startswith("v=")), "")
    if not v_cookie:
        return

    def ths_cookie(js_path="ths.js"):
        del js_path
        return f"{v_cookie};"

    cookie.ths_cookie = ths_cookie
    common = getattr(adata_module, "common", None)
    common_utils = getattr(common, "utils", None)
    if common_utils is not None:
        common_utils.cookie = cookie


def _is_etf(code: str) -> bool:
    return code.startswith(("51", "15", "58", "56"))


def _is_index_security(security: str) -> bool:
    code = _security_code(security)
    if security.endswith(".XSHG") and code.startswith(("000", "880", "881", "882", "883", "884", "885", "886")):
        return True
    return security.endswith(".XSHE") and code.startswith("399")


def _security_types(types) -> list[str]:
    if types is None:
        return ["stock"]
    if isinstance(types, str):
        return [types]
    return list(types)


def _calendar_dates(raw: pd.DataFrame) -> list[date]:
    if raw is None or raw.empty:
        return []
    date_column = next((column for column in ("trade_date", "cal_date", "calendar_date", "date") if column in raw.columns), None)
    if date_column is None:
        raise ValueError("trade calendar data does not include a date column")
    data = raw.copy()
    open_column = next((column for column in ("is_trade", "is_open", "trade_status", "status", "open") if column in data.columns), None)
    if open_column is not None:
        data = data[data[open_column].map(_is_open_trade_day)]
    days = {_coerce_date(value) for value in data[date_column].dropna().tolist()}
    return sorted(days)


def _is_open_trade_day(value) -> bool:
    if value is None or pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return int(value) == 1
    text = str(value).strip().lower()
    return text in {"1", "true", "t", "yes", "y", "open", "trade", "trading", "交易", "是"}


def _infer_security_type(code: str) -> str | None:
    security_code = _security_code(code)
    if _is_etf(security_code):
        return "fund"
    if _is_index_security(code):
        return "index"
    if code.endswith((".XSHE", ".XSHG")) or security_code[:1] in {"0", "3", "6", "8"}:
        return "stock"
    return None


def _parse_unit(unit: str) -> tuple[int, str]:
    if not isinstance(unit, str) or len(unit) < 2 or unit[-1] not in {"d", "m"}:
        raise ValueError("unit must use Xd or Xm format")
    try:
        value = int(unit[:-1])
    except ValueError as exc:
        raise ValueError("unit must use Xd or Xm format") from exc
    if value <= 0:
        raise ValueError("unit value must be positive")
    return value, unit[-1]


def _normalize_frequency(frequency: str) -> tuple[int, str]:
    aliases = {"daily": "1d", "day": "1d", "minute": "1m"}
    return _parse_unit(aliases.get(frequency, frequency))


def _history_end(unit_kind: str) -> datetime:
    now = datetime.now()
    if unit_kind == "d":
        return now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    return now.replace(second=0, microsecond=0) - timedelta(minutes=1)


def _history_start(count: int, unit_value: int, unit_kind: str, end_dt: datetime) -> datetime:
    buffer_days = int(count * unit_value * 1.8) + 30 if unit_kind == "d" else int(math.ceil(count * unit_value / 240) * 1.8) + 15
    return end_dt - timedelta(days=buffer_days)


def _validate_count(count: int) -> None:
    if not isinstance(count, int) or count <= 0:
        raise ValueError("count must be a positive integer")


def _validate_fq(fq: str | None) -> None:
    if fq not in {"pre", "post", None}:
        raise ValueError("fq must be 'pre', 'post', or None")


def _validate_fields(fields: list[str], unit_value: int) -> None:
    if not fields:
        raise ValueError("fields must not be empty")
    if unit_value > 1 and any(field not in _MULTI_PERIOD_FIELDS for field in fields):
        raise NotImplementedError("multi-period bars only support open, close, high, low, volume, and money")


def _field_list(fields) -> list[str]:
    return [fields] if isinstance(fields, str) else list(fields)


def _resample_bars(data: pd.DataFrame, unit_value: int, unit_kind: str, fields: list[str]) -> pd.DataFrame:
    if unit_value == 1 or data.empty:
        return data[fields]
    del unit_kind
    result = pd.DataFrame(index=data.index)
    if "open" in data:
        result["open"] = data["open"].rolling(unit_value).apply(lambda values: values[0], raw=True)
    if "close" in data:
        result["close"] = data["close"]
    if "high" in data:
        result["high"] = data["high"].rolling(unit_value).max()
    if "low" in data:
        result["low"] = data["low"].rolling(unit_value).min()
    if "volume" in data:
        result["volume"] = data["volume"].rolling(unit_value).sum()
    if "money" in data:
        result["money"] = data["money"].rolling(unit_value).sum()
    result = result.iloc[unit_value - 1 :].dropna(how="all")
    for field in fields:
        if field not in result:
            result[field] = np.nan
    return result[fields]


def _coerce_end_date(value, unit_kind: str) -> datetime:
    if value is None:
        return _history_end(unit_kind)
    dt = _coerce_datetime(value)
    if unit_kind == "d":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return dt.replace(second=0, microsecond=0)


def _coerce_start_date(value, unit_kind: str) -> datetime:
    dt = _coerce_datetime(value)
    if unit_kind == "d":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return dt.replace(second=0, microsecond=0)


def _coerce_datetime(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        return pd.to_datetime(value).to_pydatetime()
    raise TypeError("date values must be strings, date, or datetime")


def _coerce_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return pd.to_datetime(value).date()
    raise TypeError("date values must be strings, date, or datetime")


def _estimated_count(start_dt: datetime, end_dt: datetime, unit_value: int, unit_kind: str) -> int:
    if unit_kind == "d":
        return max((end_dt - start_dt).days // unit_value + 1, 1)
    return max(int((end_dt - start_dt).total_seconds() // 60 // unit_value) + 1, 1)


def _jq_code(code: Any) -> str:
    text = str(code)
    if "." in text:
        return text
    return f"{text}.XSHG" if text.startswith(("5", "6", "9")) else f"{text}.XSHE"


def _jq_stock_code(code: Any, exchange: Any = None) -> str:
    text = str(code).zfill(6)
    exchange_text = str(exchange or "").upper()
    if exchange_text == "SH":
        return f"{text}.XSHG"
    if exchange_text == "SZ":
        return f"{text}.XSHE"
    if exchange_text == "BJ":
        return f"{text}.XSHG"
    return _jq_code(text)


def _jq_index_code(code: Any) -> str:
    text = str(code).zfill(6)
    return f"{text}.XSHE" if text.startswith("399") else f"{text}.XSHG"


def _first_row_value(row: Any, *keys: str):
    for key in keys:
        value = _row_get(row, key)
        if value is not None and not pd.isna(value):
            return value
    return None


def _float_or_none(value) -> float | None:
    return None if value is None or pd.isna(value) else float(value)


def _bool_or_none(value) -> bool | None:
    return None if value is None or pd.isna(value) else bool(value)


def _row_get(row: Any, key: str, default=None):
    value = row.get(key, default)
    return default if value is None else value


def _none_if_nan(value):
    return None if value is None or pd.isna(value) else value


def _parse_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return datetime.strptime(value, "%Y-%m-%d").date()
    return None
