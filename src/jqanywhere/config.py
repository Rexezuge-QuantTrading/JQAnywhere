"""Configuration loading for JQAnywhere."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

DATA_PROVIDERS = {"empty", "adata"}
BROKER_PROVIDERS = {"paper"}
PERSISTENCE_PROVIDERS = {"memory", "dynamodb"}
NOTIFICATION_PROVIDERS = {"console", "sns"}
RUNTIME_MODES = {"paper"}


@dataclass(frozen=True)
class StrategyConfig:
    id: str
    path: Path


@dataclass(frozen=True)
class RuntimeConfig:
    timezone: str = "Asia/Shanghai"
    mode: str = "paper"


@dataclass(frozen=True)
class DataConfig:
    provider: str = "empty"
    strict_current_date: bool = False


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
    data: DataConfig
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
    market_data = data.get("data", {})
    broker_data = data.get("broker", {})
    persistence_data = data.get("persistence", {})
    notification_data = data.get("notifications", {})

    config = AppConfig(
        strategy=StrategyConfig(id=strategy_id, path=Path(strategy_path)),
        runtime=RuntimeConfig(
            timezone=os.getenv("JQANYWHERE_TIMEZONE", runtime_data.get("timezone", "Asia/Shanghai")),
            mode=os.getenv("JQANYWHERE_MODE", runtime_data.get("mode", "paper")),
        ),
        data=DataConfig(
            provider=os.getenv("JQANYWHERE_DATA_PROVIDER", market_data.get("provider", "empty")),
            strict_current_date=_bool_env("JQANYWHERE_DATA_STRICT_CURRENT_DATE", market_data.get("strict_current_date", False)),
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
    validate_config(config)
    return config


def validate_config(config: AppConfig) -> None:
    errors = []
    _validate_choice(errors, "runtime.mode", config.runtime.mode, RUNTIME_MODES)
    _validate_choice(errors, "data.provider", config.data.provider, DATA_PROVIDERS)
    _validate_choice(errors, "broker.provider", config.broker.provider, BROKER_PROVIDERS)
    _validate_choice(errors, "persistence.provider", config.persistence.provider, PERSISTENCE_PROVIDERS)
    _validate_choice(errors, "notifications.provider", config.notifications.provider, NOTIFICATION_PROVIDERS)
    if config.broker.initial_cash < 0:
        errors.append("broker.initial_cash must be non-negative")
    if errors:
        raise ValueError("Invalid JQAnywhere config: " + "; ".join(errors))


def _validate_choice(errors: list[str], name: str, value: str, allowed: set[str]) -> None:
    if value not in allowed:
        errors.append(f"{name} must be one of {', '.join(sorted(allowed))}; got {value!r}")


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return bool(default)
    return value.lower() in {"1", "true", "yes", "on"}
