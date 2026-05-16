import sys
import types

import pandas as pd

from jqanywhere.data.adata_provider import ADataMarketDataProvider


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
    monkeypatch.setitem(sys.modules, "adata", types.SimpleNamespace(fund=types.SimpleNamespace(market=market)))

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
    monkeypatch.setitem(sys.modules, "adata", types.SimpleNamespace(fund=types.SimpleNamespace(market=market)))

    provider = ADataMarketDataProvider()
    current_data = provider.get_current_data()

    assert current_data["518880.XSHG"].paused is False
    assert current_data["518880.XSHG"].last_price == 1.23
    assert calls == [{"fund_code": "518880"}]
