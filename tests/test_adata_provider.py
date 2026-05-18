import sys
import types

import pandas as pd
import pytest

from jqanywhere.data.adata_provider import ADataMarketDataProvider


def _stock_history():
    return pd.DataFrame(
        {
            "trade_date": ["2026-05-11", "2026-05-12", "2026-05-13", "2026-05-14", "2026-05-15"],
            "open": [9.0, 10.0, 11.0, 12.0, 13.0],
            "close": [9.5, 10.5, 11.5, 12.5, 13.5],
            "high": [10.0, 11.0, 12.0, 13.0, 14.0],
            "low": [8.0, 9.0, 10.0, 11.0, 12.0],
            "amount": [90.0, 100.0, 110.0, 120.0, 130.0],
            "volume": [900, 1000, 0, 1200, 1300],
            "factor": [1.0, 1.1, 1.2, 1.3, 1.4],
            "pre_close": [8.5, 9.5, 10.5, 11.5, 12.5],
            "high_limit": [10.45, 11.55, 12.65, 13.75, 14.85],
            "low_limit": [8.55, 9.45, 10.35, 11.25, 12.15],
        }
    )


def _install_adata(monkeypatch, *, stock_market=None, fund_market=None, stock_info=None):
    cookie_module = types.SimpleNamespace(ths_cookie=lambda js_path="ths.js": "")
    utils_module = types.SimpleNamespace(cookie=cookie_module)
    headers_module = types.SimpleNamespace(text_headers={"Cookie": "foo=bar; v=static-token; baz=qux"})
    common_module = types.SimpleNamespace(utils=utils_module, headers=types.SimpleNamespace(ths_headers=headers_module))
    monkeypatch.setitem(
        sys.modules,
        "adata",
        types.SimpleNamespace(
            common=common_module,
            stock=types.SimpleNamespace(market=stock_market or types.SimpleNamespace(), info=stock_info or types.SimpleNamespace()),
            fund=types.SimpleNamespace(market=fund_market or types.SimpleNamespace()),
        ),
    )
    monkeypatch.setitem(sys.modules, "adata.common", common_module)
    monkeypatch.setitem(sys.modules, "adata.common.utils", utils_module)
    monkeypatch.setitem(sys.modules, "adata.common.utils.cookie", cookie_module)
    monkeypatch.setitem(sys.modules, "adata.common.headers", types.SimpleNamespace(ths_headers=headers_module))
    monkeypatch.setitem(sys.modules, "adata.common.headers.ths_headers", headers_module)
    return cookie_module


def test_adata_patches_static_ths_cookie_when_mini_racer_is_unavailable(monkeypatch):
    cookie_module = _install_adata(monkeypatch)

    class BrokenMiniRacer:
        def __init__(self):
            raise RuntimeError("Native library not available")

    monkeypatch.setitem(sys.modules, "py_mini_racer", types.SimpleNamespace(MiniRacer=BrokenMiniRacer))

    ADataMarketDataProvider()

    assert cookie_module.ths_cookie() == "v=static-token;"


def test_adata_attribute_history_maps_etf_fields(monkeypatch):
    market = types.SimpleNamespace(
        get_market_etf=lambda **kwargs: pd.DataFrame(
            {
                "trade_date": ["2026-05-13", "2026-05-14", "2026-05-15"],
                "close": [1.0, 1.1, 1.2],
                "amount": [100.0, 110.0, 120.0],
                "volume": [1000, 1000, 1000],
            }
        ),
        get_market_etf_current=lambda **kwargs: pd.DataFrame(),
    )
    _install_adata(monkeypatch, fund_market=market)

    provider = ADataMarketDataProvider()
    result = provider.attribute_history("518880.XSHG", 2, "1d", ["close", "money"], True, True, "pre")

    assert list(result.columns) == ["close", "money"]
    assert result["close"].tolist() == [1.1, 1.2]
    assert result["money"].tolist() == [110.0, 120.0]


def test_adata_current_data_fetches_lazily(monkeypatch):
    calls = []

    def get_market_etf_current(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame({"price": [1.23], "volume": [1000], "trade_date": ["2026-05-15"]})

    market = types.SimpleNamespace(get_market_etf_current=get_market_etf_current)
    _install_adata(monkeypatch, fund_market=market)

    provider = ADataMarketDataProvider()
    current_data = provider.get_current_data()

    assert current_data["518880.XSHG"].paused is False
    assert current_data["518880.XSHG"].last_price == 1.23
    assert calls == [{"fund_code": "518880"}]


def test_adata_attribute_history_supports_dict_return_and_paused_filter(monkeypatch):
    market = types.SimpleNamespace(get_market=lambda **kwargs: _stock_history())
    _install_adata(monkeypatch, stock_market=market)

    provider = ADataMarketDataProvider()
    result = provider.attribute_history("000001.XSHE", 4, "1d", ["close", "paused"], True, False, "pre")

    assert set(result) == {"close", "paused"}
    assert result["close"].tolist() == [9.5, 10.5, 12.5, 13.5]
    assert result["paused"].tolist() == [0, 0, 0, 0]


def test_adata_attribute_history_fills_paused_price_and_zeroes_turnover(monkeypatch):
    market = types.SimpleNamespace(get_market=lambda **kwargs: _stock_history())
    _install_adata(monkeypatch, stock_market=market)

    provider = ADataMarketDataProvider()
    result = provider.attribute_history("000001.XSHE", 5, "1d", ["close", "volume", "money", "paused"], False, True, "pre")

    assert result["close"].tolist() == [9.5, 10.5, 11.5, 12.5, 13.5]
    assert result["paused"].tolist() == [0, 0, 1, 0, 0]
    assert result["volume"].tolist()[2] == 0
    assert result["money"].tolist()[2] == 0.0


def test_adata_attribute_history_rejects_invalid_contract_inputs(monkeypatch):
    _install_adata(monkeypatch)
    provider = ADataMarketDataProvider()

    with pytest.raises(ValueError, match="count"):
        provider.attribute_history("000001.XSHE", 0, "1d", ["close"], True, True, "pre")
    with pytest.raises(ValueError, match="fq"):
        provider.attribute_history("000001.XSHE", 1, "1d", ["close"], True, True, "bad")
    with pytest.raises(NotImplementedError, match="multi-period"):
        provider.attribute_history("000001.XSHE", 1, "2d", ["factor"], True, True, "pre")


def test_adata_attribute_history_synthesizes_sliding_multi_period_bars(monkeypatch):
    market = types.SimpleNamespace(get_market=lambda **kwargs: _stock_history())
    _install_adata(monkeypatch, stock_market=market)

    provider = ADataMarketDataProvider()
    result = provider.attribute_history("000001.XSHE", 2, "2d", ["open", "close", "high", "low", "volume", "money"], False, True, "pre")

    assert result.index.tolist() == pd.to_datetime(["2026-05-14", "2026-05-15"]).tolist()
    assert result["open"].tolist() == [11.0, 12.0]
    assert result["close"].tolist() == [12.5, 13.5]
    assert result["high"].tolist() == [13.0, 14.0]
    assert result["low"].tolist() == [10.0, 11.0]
    assert result["volume"].tolist() == [1200.0, 2500.0]
    assert result["money"].tolist() == [120.0, 250.0]


def test_adata_get_price_single_security_with_explicit_date_range(monkeypatch):
    calls = []

    def get_market(**kwargs):
        calls.append(kwargs)
        return _stock_history()

    market = types.SimpleNamespace(get_market=get_market)
    _install_adata(monkeypatch, stock_market=market)

    provider = ADataMarketDataProvider()
    result = provider.get_price(
        "000001.XSHE",
        start_date="2026-05-12",
        end_date="2026-05-14",
        frequency="daily",
        fields=["open", "money"],
        fq=None,
    )

    assert result.index.tolist() == pd.to_datetime(["2026-05-12", "2026-05-13", "2026-05-14"]).tolist()
    assert result["open"].tolist() == [10.0, 11.0, 12.0]
    assert result["money"].tolist() == [100.0, 0.0, 120.0]
    assert calls[0]["adjust_type"] == 0


def test_adata_get_price_multiple_securities_panel_shape(monkeypatch):
    def get_market(**kwargs):
        data = _stock_history()
        if kwargs["stock_code"] == "000002":
            data = data.assign(close=data["close"] + 100)
        return data

    market = types.SimpleNamespace(get_market=get_market)
    _install_adata(monkeypatch, stock_market=market)

    provider = ADataMarketDataProvider()
    result = provider.get_price(["000001.XSHE", "000002.XSHE"], end_date="2026-05-15", count=2, fields=["close"], panel=True)

    assert list(result) == ["close"]
    assert list(result["close"].columns) == ["000001.XSHE", "000002.XSHE"]
    assert result["close"]["000001.XSHE"].tolist() == [12.5, 13.5]
    assert result["close"]["000002.XSHE"].tolist() == [112.5, 113.5]


def test_adata_get_price_panel_false_multiindex(monkeypatch):
    market = types.SimpleNamespace(get_market=lambda **kwargs: _stock_history())
    _install_adata(monkeypatch, stock_market=market)

    provider = ADataMarketDataProvider()
    result = provider.get_price(["000001.XSHE", "000002.XSHE"], end_date="2026-05-15", count=1, fields=["close"], panel=False)

    assert result.index.names == ["security", "datetime"]
    assert result.loc[("000001.XSHE", pd.Timestamp("2026-05-15")), "close"] == 13.5


def test_adata_get_price_rejects_ambiguous_and_panel_skip_paused(monkeypatch):
    _install_adata(monkeypatch)
    provider = ADataMarketDataProvider()

    with pytest.raises(ValueError, match="mutually exclusive"):
        provider.get_price("000001.XSHE", start_date="2026-05-01", count=1)
    with pytest.raises(ValueError, match="panel=False"):
        provider.get_price(["000001.XSHE", "000002.XSHE"], count=1, skip_paused=True, panel=True)


def test_adata_minute_history_excludes_current_minute_and_maps_trade_time(monkeypatch):
    def get_market_min(**kwargs):
        return pd.DataFrame(
            {
                "trade_time": ["2026-05-15 09:30:00", "2026-05-15 09:31:00", "2026-05-15 09:32:00"],
                "close": [1.0, 2.0, 3.0],
                "volume": [100, 200, 300],
            }
        )

    market = types.SimpleNamespace(get_market_min=get_market_min)
    _install_adata(monkeypatch, stock_market=market)

    provider = ADataMarketDataProvider()
    result = provider.get_price("000001.XSHE", end_date="2026-05-15 09:31:00", count=2, frequency="1m", fields=["close", "volume"])

    assert result.index.tolist() == pd.to_datetime(["2026-05-15 09:30:00", "2026-05-15 09:31:00"]).tolist()
    assert result["close"].tolist() == [1.0, 2.0]


def test_adata_current_data_maps_supported_attributes(monkeypatch):
    market = types.SimpleNamespace(
        get_market_current=lambda **kwargs: pd.DataFrame(
            {
                "price": [12.3],
                "volume": [100],
                "high_limit": [13.53],
                "low_limit": [11.07],
                "is_st": [False],
                "open": [12.0],
                "name": ["Ping An Bank"],
                "industry_code": ["J66"],
            }
        )
    )
    _install_adata(monkeypatch, stock_market=market)

    data = ADataMarketDataProvider().get_current_data()["000001.XSHE"]

    assert data.paused is False
    assert data.last_price == 12.3
    assert data.high_limit == 13.53
    assert data.low_limit == 11.07
    assert data.is_st is False
    assert data.day_open == 12.0
    assert data.name == "Ping An Bank"
    assert data.industry_code == "J66"


def test_adata_get_index_stocks_maps_codes(monkeypatch):
    info = types.SimpleNamespace(get_index_stocks=lambda **kwargs: pd.DataFrame({"stock_code": ["600000", "000001"]}))
    _install_adata(monkeypatch, stock_info=info)

    result = ADataMarketDataProvider().get_index_stocks("000300.XSHG", date="2026-05-15")

    assert result == ["600000.XSHG", "000001.XSHE"]


def test_adata_etf_minute_history_fails_explicitly(monkeypatch):
    _install_adata(monkeypatch, fund_market=types.SimpleNamespace())
    provider = ADataMarketDataProvider()

    with pytest.raises(NotImplementedError, match="ETF minute"):
        provider.get_price("518880.XSHG", end_date="2026-05-15 09:31:00", count=1, frequency="1m", fields=["close"])
