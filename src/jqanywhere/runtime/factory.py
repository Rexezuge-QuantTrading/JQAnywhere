"""Runtime dependency factory."""

from __future__ import annotations

import os

from jqanywhere.broker.paper import PaperBroker
from jqanywhere.config import AppConfig
from jqanywhere.data.adata_provider import ADataMarketDataProvider
from jqanywhere.data.base import EmptyMarketDataProvider
from jqanywhere.notifications.console import ConsoleNotifier
from jqanywhere.notifications.sns import SnsNotifier
from jqanywhere.persistence.dynamodb import DynamoDBStateStore
from jqanywhere.persistence.memory import MemoryStateStore
from jqanywhere.runtime.engine import RuntimeEngine


def build_engine(config: AppConfig) -> RuntimeEngine:
    data = (
        ADataMarketDataProvider(strict_current_date=config.data.strict_current_date)
        if config.data.provider == "adata"
        else EmptyMarketDataProvider()
    )
    state_store = (
        DynamoDBStateStore(config.persistence.table_name, endpoint_url=os.getenv("AWS_ENDPOINT_URL"))
        if config.persistence.provider == "dynamodb"
        else MemoryStateStore()
    )
    notifier = SnsNotifier(endpoint_url=os.getenv("AWS_ENDPOINT_URL")) if config.notifications.provider == "sns" else ConsoleNotifier()
    return RuntimeEngine(
        strategy_id=config.strategy.id,
        strategy_path=config.strategy.path,
        data=data,
        broker=PaperBroker(),
        state_store=state_store,
        notifier=notifier,
        initial_cash=config.broker.initial_cash,
        timezone=config.runtime.timezone,
    )
