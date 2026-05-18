"""Remote MiniQMT-agent-backed market data provider."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd

from jqanywhere.data.base import MarketDataProvider, _filter_trade_days
from jqanywhere.jqcompat.types import CurrentData, SecurityInfo


class LazyRemoteCurrentData(dict):
    def __init__(self, fetch_one):
        super().__init__()
        self._fetch_one = fetch_one

    def __missing__(self, security: str) -> CurrentData:
        value = self._fetch_one(security)
        self[security] = value
        return value


class RemoteMiniQmtMarketDataProvider(MarketDataProvider):
    """Market data adapter that talks to a separately deployed MiniQMT agent."""

    def __init__(self, client):
        self.client = client

    def attribute_history(self, security: str, count: int, unit: str, fields, skip_paused: bool, df: bool, fq: str | None):
        field_list = _field_list(fields)
        response = self.client.post(
            "/v1/market/history",
            {
                "security": security,
                "count": count,
                "unit": unit,
                "fields": field_list,
                "skip_paused": skip_paused,
                "fq": fq,
            },
        )
        data = _frame_from_rows(_rows(response), field_list)
        return data if df else {field: data[field].to_numpy() for field in field_list}

    def get_current_data(self) -> dict[str, CurrentData]:
        return LazyRemoteCurrentData(self._fetch_current_data)

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
        response = self.client.post(
            "/v1/market/price",
            {
                "securities": securities,
                "start_date": _date_value(start_date),
                "end_date": _date_value(end_date),
                "frequency": frequency,
                "fields": field_list,
                "skip_paused": skip_paused,
                "fq": fq,
                "count": count,
                "fill_paused": fill_paused,
            },
        )
        frames = _frames_from_price_response(response, securities, field_list)
        if len(securities) == 1:
            return frames[securities[0]]
        if panel:
            return {field: pd.concat({code: frames[code][field] for code in securities}, axis=1) for field in field_list}
        return pd.concat(frames, names=["security", "datetime"])

    def get_index_stocks(self, index_symbol: str, date=None) -> list[str]:
        response = self.client.post("/v1/market/index-stocks", {"index_symbol": index_symbol, "date": _date_value(date)})
        return list(response.get("securities", response.get("stocks", [])))

    def get_all_securities(self, types=None, date=None):
        response = self.client.post("/v1/market/securities", {"types": types, "date": _date_value(date)})
        rows = response.get("securities", response.get("rows", []))
        data = pd.DataFrame(rows)
        if data.empty:
            return pd.DataFrame(columns=["display_name", "name", "start_date", "end_date", "type"])
        if "code" in data.columns:
            data = data.set_index("code")
        return data

    def get_security_info(self, code: str) -> SecurityInfo:
        response = self.client.post("/v1/market/security-info", {"code": code})
        payload = response.get("security", response)
        return SecurityInfo(
            code=payload["code"],
            display_name=payload.get("display_name"),
            name=payload.get("name"),
            start_date=payload.get("start_date"),
            end_date=payload.get("end_date"),
            type=payload.get("type"),
        )

    def get_trade_days(self, start_date=None, end_date=None, count=None) -> list[date]:
        response = self.client.post(
            "/v1/market/trade-days", {"start_date": _date_value(start_date), "end_date": _date_value(end_date), "count": count}
        )
        days = [_coerce_date(day) for day in response.get("days", [])]
        return _filter_trade_days(days, start_date, end_date, count)

    def get_all_trade_days(self) -> list[date]:
        response = self.client.post("/v1/market/trade-days", {})
        return [_coerce_date(day) for day in response.get("days", [])]

    def _fetch_current_data(self, security: str) -> CurrentData:
        response = self.client.post("/v1/market/current", {"securities": [security]})
        payload = _first_current_payload(response, security)
        return CurrentData(
            security=security,
            paused=bool(payload.get("paused", False)),
            last_price=_float_or_none(payload.get("last_price")),
            high_limit=_float_or_none(payload.get("high_limit")),
            low_limit=_float_or_none(payload.get("low_limit")),
            is_st=payload.get("is_st"),
            day_open=_float_or_none(payload.get("day_open")),
            name=payload.get("name"),
            industry_code=payload.get("industry_code"),
        )


def _field_list(fields) -> list[str]:
    return [fields] if isinstance(fields, str) else list(fields)


def _rows(response: dict[str, Any]) -> list[dict[str, Any]]:
    return list(response.get("rows", response.get("data", [])))


def _frame_from_rows(rows: list[dict[str, Any]], fields: list[str]) -> pd.DataFrame:
    data = pd.DataFrame(rows)
    if data.empty:
        return pd.DataFrame(columns=fields)
    index_column = next((column for column in ("datetime", "date", "time") if column in data.columns), None)
    if index_column is not None:
        data.index = pd.to_datetime(data.pop(index_column))
    for field in fields:
        if field not in data.columns:
            data[field] = pd.NA
    return data[fields]


def _frames_from_price_response(response: dict[str, Any], securities: list[str], fields: list[str]) -> dict[str, pd.DataFrame]:
    payload = response.get("securities")
    if isinstance(payload, dict):
        return {code: _frame_from_rows(_rows(rows if isinstance(rows, dict) else {"rows": rows}), fields) for code, rows in payload.items()}
    if isinstance(payload, list):
        return {item["security"]: _frame_from_rows(_rows(item), fields) for item in payload}
    if len(securities) == 1:
        return {securities[0]: _frame_from_rows(_rows(response), fields)}
    return {code: pd.DataFrame(columns=fields) for code in securities}


def _first_current_payload(response: dict[str, Any], security: str) -> dict[str, Any]:
    current = response.get("current", response.get("securities", []))
    if isinstance(current, dict):
        return dict(current.get(security, {}))
    for item in current:
        if item.get("security") == security:
            return dict(item)
    return {"security": security, "paused": True}


def _date_value(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def _coerce_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return pd.to_datetime(value).date()


def _float_or_none(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)
