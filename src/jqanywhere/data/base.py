"""Market data provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import date, datetime

from jqanywhere.jqcompat.types import CurrentData, SecurityInfo

try:
    import pandas as pd
except ModuleNotFoundError:  # pragma: no cover - dependency is installed in normal package usage.
    pd = None


class MarketDataProvider(ABC):
    """JoinQuant-compatible market data provider contract.

    Implementations should preserve JoinQuant's no-future-data behavior: daily history
    excludes the current day even after close, and minute history excludes the current
    minute. Unsupported data semantics should fail explicitly rather than returning
    silently misleading financial data.
    """

    @abstractmethod
    def attribute_history(self, security: str, count: int, unit: str, fields, skip_paused: bool, df: bool, fq: str | None):
        """Return historical bars for one security and multiple fields.

        JoinQuant API: ``attribute_history(security, count, unit='1d',
        fields=['open', 'close', 'high', 'low', 'volume', 'money'],
        skip_paused=True, df=True, fq='pre')``.

        Parameters:
            security: Security code, for example ``"000001.XSHE"``.
            count: Number of rows to return.
            unit: Bar size in ``"Xd"`` or ``"Xm"`` form, where X is a positive
                integer. For X > 1, JoinQuant only supports standard OHLCV fields:
                ``open``, ``close``, ``high``, ``low``, ``volume``, ``money``.
            fields: Field name or iterable of field names. JoinQuant basic fields
                include ``open``, ``close``, ``low``, ``high``, ``volume``, ``money``,
                ``factor``, ``high_limit``, ``low_limit``, ``avg``, ``pre_close``,
                and ``paused``.
            skip_paused: Whether to skip non-trading rows, including suspended,
                pre-listing, and post-delisting dates. If false, suspended rows should
                be filled from previous data where possible; pre-listing and
                post-delisting rows should remain ``NaN``.
            df: If true, return a ``pandas.DataFrame`` indexed by ``datetime`` with
                fields as columns. If false, return ``dict[str, numpy.ndarray]`` keyed
                by field name.
            fq: Adjustment mode for stock/fund price fields, volume fields, and
                ``factor``: ``"pre"`` for pre-adjusted prices, ``None`` for actual
                prices, or ``"post"`` for post-adjusted prices.
        """
        raise NotImplementedError

    @abstractmethod
    def get_current_data(self) -> dict[str, CurrentData]:
        """Return lazy current-period data keyed by security code.

        JoinQuant API: ``get_current_data()``. The returned mapping should fetch each
        security on demand when ``current_data[security]`` is accessed. Values expose
        JoinQuant-style attributes where supported: ``last_price`` (previous close
        before 09:30), ``high_limit``, ``low_limit``, ``paused``, ``is_st``,
        ``day_open`` (available no earlier than about 09:27), ``name``, and
        ``industry_code``.

        Results are only valid for the current trading day and should not be persisted
        across days. JoinQuant limits this API to securities in their trading session.
        """
        raise NotImplementedError

    def get_price(self, security, *args, **kwargs):
        """Return historical prices for one or more securities.

        JoinQuant API: ``get_price(security, start_date=None, end_date=None,
        frequency='daily', fields=None, skip_paused=False, fq='pre', count=None,
        panel=True, fill_paused=True)``.

        Contract highlights:
            ``security`` may be one code or a list of codes; ``count`` and
            ``start_date`` are mutually exclusive; ``end_date`` is inclusive and must
            not exceed ``context.current_dt`` in strategies; ``frequency`` supports
            ``"daily"``/``"1d"``, ``"minute"``/``"1m"``, and positive ``"Xd"`` or
            ``"Xm"`` windows. Multi-period windows are synthesized from sliding
            lower-frequency bars and, for X > 1, only standard OHLCV fields are
            supported.

        Fields default to ``open``, ``close``, ``high``, ``low``, ``volume``, and
        ``money``. JoinQuant also supports ``factor``, ``high_limit``, ``low_limit``,
        ``avg``, ``pre_close``, ``paused``, and ``open_interest`` where available.
        ``skip_paused=False`` keeps aligned time axes and fills suspended prices;
        ``fill_paused=False`` uses ``NaN`` for suspended prices. For multi-security
        requests, ``skip_paused=True`` requires ``panel=False`` because aligned panel
        axes cannot skip different dates per security.

        Return shape follows JoinQuant: one security returns a ``pandas.DataFrame``
        indexed by ``datetime`` with fields as columns. Multiple securities with
        legacy ``panel=True`` return field-indexed panel-like data where each field is
        a DataFrame indexed by ``datetime`` with securities as columns; modern pandas
        users should prefer ``panel=False`` for equivalent DataFrame output.
        """
        raise NotImplementedError("JQAnywhere v0.8.0 does not implement get_price for this data provider")

    def get_index_stocks(self, index_symbol: str, date=None) -> list[str]:
        """Return tradable constituent security codes for an index on a date.

        JoinQuant API: ``get_index_stocks(index_symbol, date=None)``.
        ``index_symbol`` is an index code such as ``"000300.XSHG"``. ``date`` may be
        a ``YYYY-MM-DD`` string, ``datetime.date``, ``datetime.datetime``, or ``None``.
        In JoinQuant, default dates differ between backtest and research contexts. In
        JQAnywhere, callers should pass an explicit event date when provider behavior
        must be deterministic. The return value is a list of stock codes.
        """
        raise NotImplementedError("JQAnywhere v0.8.0 does not implement get_index_stocks for this data provider")

    def get_all_securities(self, types=None, date=None):
        """Return security metadata as a JoinQuant-style DataFrame indexed by code."""
        raise NotImplementedError("JQAnywhere v0.8.0 does not implement get_all_securities for this data provider")

    def get_security_info(self, code: str) -> SecurityInfo:
        """Return one security's JoinQuant-style metadata object."""
        raise NotImplementedError("JQAnywhere v0.8.0 does not implement get_security_info for this data provider")

    def get_trade_days(self, start_date=None, end_date=None, count=None) -> list[date]:
        """Return trading days between dates, or the last ``count`` days up to ``end_date``."""
        raise NotImplementedError("JQAnywhere v0.8.0 does not implement get_trade_days for this data provider")

    def get_all_trade_days(self) -> list[date]:
        """Return all trading days known by this data provider."""
        raise NotImplementedError("JQAnywhere v0.8.0 does not implement get_all_trade_days for this data provider")

    def get_fundamentals(self, query, date=None, statDate=None):
        """Return fundamentals for a JoinQuant-style query object."""
        raise NotImplementedError("JQAnywhere v0.8.0 does not implement get_fundamentals for this data provider")

    def get_valuation(self, security, start_date=None, end_date=None, fields=None, count=None):
        """Return valuation fields for one or more securities."""
        raise NotImplementedError("JQAnywhere v0.8.0 does not implement get_valuation for this data provider")

    def get_industry(self, security, date=None):
        """Return JoinQuant-shaped industry metadata keyed by security."""
        raise NotImplementedError("JQAnywhere v0.8.0 does not implement get_industry for this data provider")

    def get_extras(self, info, security_list, start_date=None, end_date=None, df=True, count=None):
        """Return JoinQuant-style extras such as ETF unit net value."""
        raise NotImplementedError("JQAnywhere v0.8.0 does not implement get_extras for this data provider")

    def get_money_flow(self, security_list, start_date=None, end_date=None, fields=None, count=None):
        """Return JoinQuant-style capital-flow data."""
        raise NotImplementedError("JQAnywhere v0.8.0 does not implement get_money_flow for this data provider")

    def get_bars(
        self, security, count: int, unit: str = "", fields=None, include_now: bool = False, end_dt=None, fq_ref_date=None, df=False
    ):
        """Return JoinQuant-style historical bars."""
        raise NotImplementedError("JQAnywhere v0.8.0 does not implement get_bars for this data provider")

    def get_industries(self, name: str, date=None):
        """Return JoinQuant-style industry list."""
        raise NotImplementedError("JQAnywhere v0.8.0 does not implement get_industries for this data provider")

    def get_industry_stocks(self, industry_code: str, date=None) -> list[str]:
        """Return JoinQuant-style industry constituents."""
        raise NotImplementedError("JQAnywhere v0.8.0 does not implement get_industry_stocks for this data provider")

    def finance_run_query(self, query):
        """Run a JoinQuant finance query."""
        raise NotImplementedError("JQAnywhere v0.8.0 does not implement finance.run_query for this data provider")


class EmptyMarketDataProvider(MarketDataProvider):
    def attribute_history(self, security: str, count: int, unit: str, fields, skip_paused: bool, df: bool, fq: str | None):
        if pd is None:
            raise ModuleNotFoundError("pandas is required for attribute_history")
        field_list = [fields] if isinstance(fields, str) else list(fields)
        data = pd.DataFrame({field: [] for field in field_list})
        return data if df else {field: data[field].to_numpy() for field in field_list}

    def get_current_data(self) -> dict[str, CurrentData]:
        return {}

    def get_trade_days(self, start_date=None, end_date=None, count=None) -> list[date]:
        return _filter_trade_days([], start_date, end_date, count)

    def get_all_trade_days(self) -> list[date]:
        return []


class StaticMarketDataProvider(MarketDataProvider):
    def __init__(
        self,
        history: dict[str, pd.DataFrame] | None = None,
        current: Iterable[str] | None = None,
        trade_days: Iterable | None = None,
        fundamentals: pd.DataFrame | None = None,
        industry: dict[str, dict] | None = None,
        extras: dict | None = None,
    ):
        self.history = history or {}
        self.current = {code: CurrentData(code, paused=False) for code in (current or [])}
        self.trade_days = sorted(_coerce_date(day) for day in (trade_days or []))
        self.fundamentals = fundamentals.copy() if fundamentals is not None else pd.DataFrame()
        self.industry = industry or {}
        self.extras = extras or {}

    def attribute_history(self, security: str, count: int, unit: str, fields, skip_paused: bool, df: bool, fq: str | None):
        if pd is None:
            raise ModuleNotFoundError("pandas is required for attribute_history")
        field_list = [fields] if isinstance(fields, str) else list(fields)
        data = self.history.get(security, pd.DataFrame(columns=field_list)).tail(count)
        data = data.reindex(columns=field_list)
        return data if df else {field: data[field].to_numpy() for field in field_list}

    def get_current_data(self) -> dict[str, CurrentData]:
        return self.current

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
        field_list = _field_list(fields or ["open", "close", "high", "low", "volume", "money"])
        frames = {code: self._price_frame(code, field_list, start_date, end_date, count) for code in securities}
        if len(securities) == 1:
            return frames[securities[0]]
        if panel:
            return {field: pd.concat({code: frames[code][field] for code in securities}, axis=1) for field in field_list}
        return _flat_price_frame(frames, field_list)

    def get_trade_days(self, start_date=None, end_date=None, count=None) -> list[date]:
        return _filter_trade_days(self.trade_days, start_date, end_date, count)

    def get_all_trade_days(self) -> list[date]:
        return list(self.trade_days)

    def get_fundamentals(self, query, date=None, statDate=None):
        return _run_fundamentals_query(self.fundamentals, query)

    def get_valuation(self, security, start_date=None, end_date=None, fields=None, count=None):
        securities = [security] if isinstance(security, str) else list(security)
        field_list = _field_list(fields or _VALUATION_FIELDS)
        data = _fundamentals_with_code(self.fundamentals)
        if data.empty:
            return pd.DataFrame(columns=field_list)
        data = data[data["code"].isin(securities)] if "code" in data.columns else data.iloc[0:0]
        if "day" in data.columns:
            if start_date is not None:
                data = data[pd.to_datetime(data["day"]) >= pd.to_datetime(start_date)]
            if end_date is not None:
                data = data[pd.to_datetime(data["day"]) <= pd.to_datetime(end_date)]
        if count is not None:
            data = data.tail(count * max(len(securities), 1))
        _require_columns(data, field_list, "get_valuation")
        return data[field_list].reset_index(drop=True)

    def get_industry(self, security, date=None):
        securities = [security] if isinstance(security, str) else list(security)
        return {code: self.industry.get(code, {}) for code in securities}

    def get_extras(self, info, security_list, start_date=None, end_date=None, df=True, count=None):
        securities = [security_list] if isinstance(security_list, str) else list(security_list)
        dates = _extras_dates(start_date, end_date, count)
        configured = self.extras.get(info, {})
        if isinstance(configured, pd.DataFrame):
            result = configured.reindex(columns=securities)
            if dates is not None:
                result = result.reindex(pd.to_datetime(dates)).ffill().tail(len(dates))
        else:
            result = pd.DataFrame(index=pd.to_datetime(dates if dates is not None else [date.today()]))
            for code in securities:
                result[code] = configured.get(code, pd.NA) if isinstance(configured, dict) else pd.NA
        return result if df else {code: result[code].to_numpy() for code in result.columns}

    def get_money_flow(self, security_list, start_date=None, end_date=None, fields=None, count=None):
        securities = [security_list] if isinstance(security_list, str) else list(security_list)
        field_list = _field_list(fields or ["date", "sec_code", "change_pct"])
        frames = []
        for code in securities:
            frame = self._price_frame(code, ["close"], start_date, end_date, None).copy()
            if count is not None:
                frame = frame.tail(count + (1 if "change_pct" in field_list else 0))
            data = pd.DataFrame(index=frame.index)
            data["date"] = data.index.date
            data["sec_code"] = code
            if "change_pct" in field_list:
                data["change_pct"] = frame["close"].pct_change() * 100
            data = data.tail(count) if count is not None else data
            frames.append(data.reset_index(drop=True))
        result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=field_list)
        _require_columns(result, field_list, "get_money_flow")
        return result[field_list]

    def get_bars(
        self, security, count: int, unit: str = "", fields=None, include_now: bool = False, end_dt=None, fq_ref_date=None, df=False
    ):
        del fq_ref_date
        field_list = _field_list(fields or ["date", "open", "high", "low", "close"])
        price_fields = [field for field in field_list if field != "date"]
        result = self.get_price(security, end_date=end_dt, frequency=unit or "1d", fields=price_fields, count=count, panel=False)
        if isinstance(security, str):
            result = result.copy()
            if "date" in field_list:
                result.insert(0, "date", result.index)
        elif "date" in field_list:
            result = result.copy()
            result.insert(0, "date", result["time"])
        if not include_now:
            result = result.tail(count)
        _require_columns(result, field_list, "get_bars")
        return result[field_list] if df else result[field_list].to_records(index=False)

    def finance_run_query(self, query):
        return _run_fundamentals_query(self.extras.get("finance", pd.DataFrame()), query)

    def _price_frame(self, security: str, fields: list[str], start_date=None, end_date=None, count=None) -> pd.DataFrame:
        data = self.history.get(security, pd.DataFrame(columns=fields)).copy()
        if not isinstance(data.index, pd.DatetimeIndex):
            data.index = pd.to_datetime(data.index)
        if start_date is not None:
            data = data[data.index >= pd.to_datetime(start_date)]
        if end_date is not None:
            data = data[data.index <= pd.to_datetime(end_date)]
        if count is not None:
            data = data.tail(count)
        for field in fields:
            if field not in data.columns:
                data[field] = pd.NA
        return data[fields]


def _filter_trade_days(trade_days: list[date], start_date=None, end_date=None, count=None) -> list[date]:
    if count is not None and start_date is not None:
        raise ValueError("count and start_date are mutually exclusive")
    if count is not None and (not isinstance(count, int) or count <= 0):
        raise ValueError("count must be a positive integer")
    end = _coerce_date(end_date) if end_date is not None else date.today()
    days = [day for day in trade_days if day <= end]
    if start_date is not None:
        start = _coerce_date(start_date)
        days = [day for day in days if day >= start]
    if count is not None:
        return days[-count:]
    return days


def _coerce_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        if pd is None:
            return datetime.fromisoformat(value).date()
        return pd.to_datetime(value).date()
    raise TypeError("date values must be strings, date, or datetime")


def _field_list(fields) -> list[str]:
    return [fields] if isinstance(fields, str) else list(fields)


_VALUATION_FIELDS = [
    "code",
    "day",
    "capitalization",
    "circulating_cap",
    "market_cap",
    "circulating_market_cap",
    "turnover_ratio",
    "pe_ratio",
    "pe_ratio_lyr",
    "pb_ratio",
    "ps_ratio",
    "pcf_ratio",
]


def _flat_price_frame(frames: dict[str, pd.DataFrame], fields: list[str]) -> pd.DataFrame:
    rows = []
    for code, frame in frames.items():
        data = frame.reset_index()
        time_column = data.columns[0]
        data = data.rename(columns={time_column: "time"})
        data.insert(1, "code", code)
        rows.append(data[["time", "code", *fields]])
    if not rows:
        return pd.DataFrame(columns=["time", "code", *fields])
    return pd.concat(rows, ignore_index=True)


def _run_fundamentals_query(data: pd.DataFrame, query) -> pd.DataFrame:
    from jqanywhere.jqcompat.query import FundamentalsQuery, QueryField, QueryTable

    result = _fundamentals_with_code(data)
    if not isinstance(query, FundamentalsQuery):
        return result.reset_index(drop=True)
    for condition in query.conditions:
        mask = condition.evaluate(result).fillna(False).astype(bool)
        result = result[mask]
    if query.sort_keys:
        sort_columns = []
        ascending = []
        for index, sort_key in enumerate(query.sort_keys):
            column = f"__jq_sort_{index}"
            result[column] = sort_key.expression.evaluate(result)
            sort_columns.append(column)
            ascending.append(sort_key.ascending)
        result = result.sort_values(sort_columns, ascending=ascending, kind="mergesort")
        result = result.drop(columns=sort_columns)
    if query.limit_count is not None:
        result = result.head(query.limit_count)
    if query.fields:
        columns = []
        for query_field in query.fields:
            if isinstance(query_field, QueryTable):
                continue
            name = _query_field_column(result, query_field) if isinstance(query_field, QueryField) else str(query_field)
            if name not in result.columns:
                raise NotImplementedError(f"data provider does not expose fundamentals field: {name}")
            columns.append(name)
        if columns:
            result = result[columns]
    return result.reset_index(drop=True)


def _require_columns(data: pd.DataFrame, columns: list[str], api_name: str) -> None:
    missing = [column for column in columns if column not in data.columns]
    if missing:
        raise NotImplementedError(f"{api_name} does not expose required fields: {', '.join(missing)}")


def _query_field_column(data: pd.DataFrame, field) -> str:
    if field.full_name in data.columns:
        return field.full_name
    return field.name


def _fundamentals_with_code(data: pd.DataFrame) -> pd.DataFrame:
    result = data.copy()
    if "code" not in result.columns and result.index.name == "code":
        result = result.reset_index()
    return result


def _extras_dates(start_date=None, end_date=None, count=None):
    if count is not None:
        end = pd.to_datetime(end_date).date() if end_date is not None else date.today()
        return pd.date_range(end=end, periods=count, freq="D")
    if start_date is None and end_date is None:
        return None
    start = pd.to_datetime(start_date if start_date is not None else end_date)
    end = pd.to_datetime(end_date if end_date is not None else start_date)
    return pd.date_range(start=start, end=end, freq="D")
