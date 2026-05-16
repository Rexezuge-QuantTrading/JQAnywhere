"""Configuration loading for JQAnywhere."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StrategyConfig:
    id: str
    path: Path


@dataclass(frozen=True)
class RuntimeConfig:
    timezone: str = "Asia/Shanghai"
    mode: str = "paper"


@dataclass(frozen=True)
class BrokerConfig:
    provider: str = "paper"
    initial_cash: float = 100_000.0


@dataclass(frozen=True)
class PersistenceConfig:
    provider: str = "memory"
    table_name: str = "jqanywhere-state"


@dataclass(frozen=True)
class NotificationConfig:
    provider: str = "console"


@dataclass(frozen=True)
class AppConfig:
    strategy: StrategyConfig
    runtime: RuntimeConfig
    broker: BrokerConfig
    persistence: PersistenceConfig
    notifications: NotificationConfig


def load_config(path: str | Path | None = None) -> AppConfig:
    """Load config from TOML with environment overrides."""
    config_path = Path(path or os.getenv("JQANYWHERE_CONFIG", "jqanywhere.toml"))
    data: dict = {}
    if config_path.exists():
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))

    strategy_data = data.get("strategy", {})
    strategy_path = os.getenv("JQANYWHERE_STRATEGY_PATH", strategy_data.get("path"))
    if not strategy_path:
        raise ValueError("strategy.path or JQANYWHERE_STRATEGY_PATH is required")

    strategy_id = os.getenv("JQANYWHERE_STRATEGY_ID", strategy_data.get("id", Path(strategy_path).stem))
    runtime_data = data.get("runtime", {})
    broker_data = data.get("broker", {})
    persistence_data = data.get("persistence", {})
    notification_data = data.get("notifications", {})

    return AppConfig(
        strategy=StrategyConfig(id=strategy_id, path=Path(strategy_path)),
        runtime=RuntimeConfig(
            timezone=os.getenv("JQANYWHERE_TIMEZONE", runtime_data.get("timezone", "Asia/Shanghai")),
            mode=os.getenv("JQANYWHERE_MODE", runtime_data.get("mode", "paper")),
        ),
        broker=BrokerConfig(
            provider=os.getenv("JQANYWHERE_BROKER", broker_data.get("provider", "paper")),
            initial_cash=float(os.getenv("JQANYWHERE_INITIAL_CASH", broker_data.get("initial_cash", 100_000.0))),
        ),
        persistence=PersistenceConfig(
            provider=os.getenv("JQANYWHERE_PERSISTENCE", persistence_data.get("provider", "memory")),
            table_name=os.getenv("JQANYWHERE_STATE_TABLE", persistence_data.get("table_name", "jqanywhere-state")),
        ),
        notifications=NotificationConfig(
            provider=os.getenv("JQANYWHERE_NOTIFIER", notification_data.get("provider", "console")),
        ),
    )
