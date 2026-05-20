"""JQAnywhere CLI."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from jqanywhere.config import load_config
from jqanywhere.runtime.factory import build_engine

SUPPORTED_API = [
    "initialize(context)",
    "run_daily(func, time, reference_security='') with HH:MM, every_bar, or before_open/open/close/after_close",
    "run_weekly(func, weekday, time, reference_security='')",
    "run_monthly(func, monthday, time, reference_security='')",
    "before_trading_start(context), after_trading_end(context)",
    "g, context, log",
    "set_option, set_benchmark, set_slippage, set_order_cost, set_commission",
    "attribute_history, history, get_current_data, get_price, get_index_stocks",
    "get_all_securities, get_security_info, get_trade_days, get_all_trade_days",
    "query, valuation, balance, cash_flow, income, indicator, get_fundamentals where provider supports fundamentals",
    "get_valuation, get_industry, get_extras where provider supports those datasets",
    "record, OrderStatus, context.run_params including v0.9.0 end_date shim",
    "order, order_target, order_value, order_target_value",
    "set_universe and disable_cache",
    "official unsupported JoinQuant API names as explicit NotImplementedError stubs",
    "jqanywhere doctor",
]

UNSUPPORTED_API = [
    "handle_data",
    "finance.run_query",
    "macro.run_query",
    "tick data APIs",
    "get_trades",
    "concept, billboard, locked-shares, and call-auction data APIs",
    "research/backtest orchestration, file/message, and profiling APIs",
    "factor APIs beyond import-compatible jqfactor stubs",
    "portfolio optimizer",
    "internal tick/minute event loops; every_bar requires external per-minute invocations",
    "futures and margin trading",
]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Process JoinQuant-style live/event-driven strategy events")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Process one configured strategy event")
    run_parser.add_argument("--config", default=None)
    run_parser.add_argument("--now", default=None, help="Single event timestamp as an ISO-8601 datetime")
    run_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")

    invoke_parser = subparsers.add_parser("invoke", help="Process one event for a strategy file")
    invoke_parser.add_argument("--strategy", required=True)
    invoke_parser.add_argument("--config", default=None)
    invoke_parser.add_argument("--now", default=None, help="Single event timestamp as an ISO-8601 datetime")
    invoke_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")

    list_api_parser = subparsers.add_parser("list-api", help="List v0.9.0 API surface")
    list_api_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")

    doctor_parser = subparsers.add_parser("doctor", help="Check config and selected providers")
    doctor_parser.add_argument("--config", default=None)
    doctor_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")

    config_parser = subparsers.add_parser("config", help="Configuration helpers")
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)
    validate_parser = config_subparsers.add_parser("validate", help="Validate a config file and environment overrides")
    validate_parser.add_argument("--config", default=None)
    validate_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")

    args = parser.parse_args(argv)
    if args.command == "list-api":
        if args.json:
            print(json.dumps({"supported": SUPPORTED_API, "unsupported": UNSUPPORTED_API}, ensure_ascii=False))
            return
        for item in SUPPORTED_API:
            print(item)
        print("\nUnsupported:")
        for item in UNSUPPORTED_API:
            print(item)
        return

    if args.command == "config" and args.config_command == "validate":
        config = load_config(args.config)
        result = {"status": "valid", "strategy_id": config.strategy.id, "strategy_path": str(config.strategy.path)}
        print(json.dumps(result, ensure_ascii=False) if args.json else "Config valid")
        return

    if args.command == "doctor":
        result = _doctor(args.config)
        print(json.dumps(result, ensure_ascii=False) if args.json else _format_doctor(result))
        if result["status"] != "ok":
            raise SystemExit(1)
        return

    config = load_config(args.config)
    if args.command == "invoke":
        object.__setattr__(config.strategy, "path", Path(args.strategy))
    result = build_engine(config).run(now=_parse_datetime(args.now) if args.now else None)
    print(json.dumps(result, ensure_ascii=False, default=str) if args.json else result)
    if result["status"] == "failed":
        raise SystemExit(1)


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _doctor(config_path: str | None) -> dict:
    checks = []
    try:
        config = load_config(config_path)
    except Exception as exc:
        return {"status": "failed", "checks": [{"name": "config", "status": "failed", "message": str(exc)}]}
    checks.append({"name": "config", "status": "ok", "message": f"strategy={config.strategy.id}"})
    strategy_path_status = "ok" if config.strategy.path.exists() else "failed"
    checks.append({"name": "strategy_path", "status": strategy_path_status, "message": str(config.strategy.path)})
    checks.append({"name": "data_provider", "status": "ok", "message": config.data.provider})
    checks.append({"name": "broker_provider", "status": "ok", "message": config.broker.provider})
    checks.extend(_remote_miniqmt_checks(config))
    checks.append({"name": "persistence_provider", "status": "ok", "message": config.persistence.provider})
    checks.append({"name": "notifier", "status": "ok", "message": config.notifications.provider})
    status = "ok" if all(check["status"] == "ok" for check in checks) else "failed"
    return {"status": status, "checks": checks}


def _remote_miniqmt_checks(config) -> list[dict[str, str]]:
    checks = []
    if config.data.provider == "remote_miniqmt":
        checks.append({"name": "remote_miniqmt_data_endpoint", "status": "ok", "message": config.data.endpoint or "missing"})
        token_status = "set" if os.getenv(config.data.token_env) else "not set"
        checks.append({"name": "remote_miniqmt_data_token", "status": "ok", "message": f"{config.data.token_env} {token_status}"})
    if config.broker.provider == "remote_miniqmt":
        checks.append({"name": "remote_miniqmt_broker_endpoint", "status": "ok", "message": config.broker.endpoint or "missing"})
        checks.append({"name": "remote_miniqmt_account", "status": "ok", "message": config.broker.account_id or "missing"})
        trading_state = "enabled" if config.broker.enable_trading else "disabled/read-only"
        checks.append({"name": "remote_miniqmt_trading", "status": "ok", "message": trading_state})
    return checks


def _format_doctor(result: dict) -> str:
    lines = [f"Doctor {result['status']}"]
    lines.extend(f"{check['status']}: {check['name']} - {check['message']}" for check in result["checks"])
    return "\n".join(lines)


if __name__ == "__main__":
    main()
