"""Runtime dependency factory."""

from __future__ import annotations

import os

from jqanywhere.broker.paper import PaperBroker
from jqanywhere.broker.remote_miniqmt import RemoteMiniQmtBroker
from jqanywhere.config import AppConfig
from jqanywhere.data.adata_provider import ADataMarketDataProvider
from jqanywhere.data.base import EmptyMarketDataProvider
from jqanywhere.data.remote_miniqmt import RemoteMiniQmtMarketDataProvider
from jqanywhere.miniqmt_remote.client import MiniQmtHttpClient
from jqanywhere.notifications.console import ConsoleNotifier
from jqanywhere.notifications.sns import SnsNotifier
from jqanywhere.persistence.dynamodb import DynamoDBStateStore
from jqanywhere.persistence.memory import MemoryStateStore
from jqanywhere.runtime.engine import RuntimeEngine


def build_engine(config: AppConfig) -> RuntimeEngine:
    if config.data.provider == "adata":
        data = ADataMarketDataProvider(strict_current_date=config.data.strict_current_date)
    elif config.data.provider == "remote_miniqmt":
        data = RemoteMiniQmtMarketDataProvider(_remote_client(config.data.endpoint, config.data.token_env, config.data.timeout_seconds))
    elif config.data.provider == "empty":
        data = EmptyMarketDataProvider()
    else:
        raise ValueError(f"Unsupported data.provider: {config.data.provider}")

    if config.persistence.provider == "dynamodb":
        state_store = DynamoDBStateStore(config.persistence.table_name, endpoint_url=os.getenv("AWS_ENDPOINT_URL"))
    elif config.persistence.provider == "memory":
        state_store = MemoryStateStore()
    else:
        raise ValueError(f"Unsupported persistence.provider: {config.persistence.provider}")

    if config.notifications.provider == "sns":
        notifier = SnsNotifier(endpoint_url=os.getenv("AWS_ENDPOINT_URL"))
    elif config.notifications.provider == "console":
        notifier = ConsoleNotifier()
    else:
        raise ValueError(f"Unsupported notifications.provider: {config.notifications.provider}")

    if config.broker.provider == "paper":
        broker = PaperBroker()
    elif config.broker.provider == "remote_miniqmt":
        broker = RemoteMiniQmtBroker(
            _remote_client(config.broker.endpoint, config.broker.token_env, config.broker.timeout_seconds),
            account_id=config.broker.account_id or "",
            account_type=config.broker.account_type,
            strategy_name=config.broker.strategy_name,
            enable_trading=config.broker.enable_trading,
        )
    else:
        raise ValueError(f"Unsupported broker.provider: {config.broker.provider}")

    return RuntimeEngine(
        strategy_id=config.strategy.id,
        strategy_path=config.strategy.path,
        data=data,
        broker=broker,
        state_store=state_store,
        notifier=notifier,
        initial_cash=config.broker.initial_cash,
        timezone=config.runtime.timezone,
    )


def _remote_client(endpoint: str | None, token_env: str, timeout_seconds: float) -> MiniQmtHttpClient:
    if not endpoint:
        raise ValueError("Remote MiniQMT endpoint is required")
    return MiniQmtHttpClient(endpoint, token=os.getenv(token_env), timeout=timeout_seconds)
