"""JQAnywhere CLI."""

from __future__ import annotations

import argparse
from pathlib import Path

from jqanywhere.config import load_config
from jqanywhere.runtime.factory import build_engine

SUPPORTED_API = [
    "initialize(context)",
    "run_daily(func, time, reference_security='')",
    "g, context, log",
    "set_option, set_benchmark, set_slippage, set_order_cost, set_commission",
    "attribute_history, get_current_data",
    "order, order_target, order_value, order_target_value",
]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run JoinQuant-style strategies anywhere")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a configured strategy once")
    run_parser.add_argument("--config", default=None)

    invoke_parser = subparsers.add_parser("invoke", help="Run a strategy file once")
    invoke_parser.add_argument("--strategy", required=True)
    invoke_parser.add_argument("--config", default=None)

    subparsers.add_parser("list-api", help="List v0.1 supported API surface")

    args = parser.parse_args(argv)
    if args.command == "list-api":
        for item in SUPPORTED_API:
            print(item)
        return

    config = load_config(args.config)
    if args.command == "invoke":
        object.__setattr__(config.strategy, "path", Path(args.strategy))
    result = build_engine(config).run()
    print(result)


if __name__ == "__main__":
    main()
