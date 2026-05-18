"""Market data provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

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
        raise NotImplementedError("JQAnywhere v0.2 does not implement get_price for this data provider")

    def get_index_stocks(self, index_symbol: str, date=None) -> list[str]:
        """Return tradable constituent security codes for an index on a date.

        JoinQuant API: ``get_index_stocks(index_symbol, date=None)``.
        ``index_symbol`` is an index code such as ``"000300.XSHG"``. ``date`` may be
        a ``YYYY-MM-DD`` string, ``datetime.date``, ``datetime.datetime``, or ``None``.
        In backtests, JoinQuant's default date is ``context.current_dt``; in research,
        the default is today. The return value is a list of stock codes.
        """
        raise NotImplementedError("JQAnywhere v0.2 does not implement get_index_stocks for this data provider")

    def get_all_securities(self, types=None, date=None):
        """Return security metadata as a JoinQuant-style DataFrame indexed by code."""
        raise NotImplementedError("JQAnywhere v0.2 does not implement get_all_securities for this data provider")

    def get_security_info(self, code: str) -> SecurityInfo:
        """Return one security's JoinQuant-style metadata object."""
        raise NotImplementedError("JQAnywhere v0.2 does not implement get_security_info for this data provider")


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
