"""Optional AData-backed market data provider."""

from __future__ import annotations

from jqanywhere.data.base import EmptyMarketDataProvider


class ADataMarketDataProvider(EmptyMarketDataProvider):
    """Placeholder for the first real China-market data adapter.

    v0.1 keeps this class as an extension point. Projects can subclass or replace
    it without changing copied JoinQuant strategy code.
    """
