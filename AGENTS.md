# AGENTS.md

## Setup And Commands

- Use a project virtualenv; the known-good local flow is `python3 -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"`.
- Run formatting with `.venv/bin/ruff format .`.
- Run lint with `.venv/bin/ruff check .`; auto-fix with `.venv/bin/ruff check . --fix`.
- Run all tests with `.venv/bin/pytest`; run a focused test with `.venv/bin/pytest tests/test_runtime.py::test_simple_strategy_runs`.
- Run the example strategy through the installed CLI with `.venv/bin/jqanywhere run --config examples/jqanywhere.toml`.
- Validate configuration with `.venv/bin/jqanywhere config validate --config examples/jqanywhere.toml`; inspect API coverage with `.venv/bin/jqanywhere list-api`.

## Formatting And Linting

- Ruff is the formatter and linter source of truth in `pyproject.toml`; no Black, isort, mypy, or pre-commit config exists currently.
- Ruff targets `py313` with `line-length = 140`, double quotes, spaces, LF endings, and source roots `src`, `tests`, `examples`.
- The project requires Python `>=3.11`, is packaged as version `0.9.0`, and depends on `adata`, `boto3`, `numpy`, `pandas`, and `TA-Lib`.
- Keep the configured per-file Ruff ignores for JoinQuant compatibility: examples may use `from jqdata import *`, `src/jqanywhere/jqcompat/api.py` re-exports wildcard API types, and `src/jqdata/__init__.py` intentionally re-exports compatibility globals.

## Git Commit Messages

- Use Conventional Commits with this subject format: `<TYPE>[optional scope]: <description>`.
- Write the type in uppercase, for example `FIX`, `FEAT`, `DOCS`, `STYLE`, `REFACTOR`, `TEST`, `BUILD`, `CHORE`, `CI`, or `PERF`.
- Write the optional scope in lowercase inside parentheses, for example `FEAT(runtime): Add Scheduled Job State`.
- Write the description as concise human-readable words with spaces, capitalizing the first letter of each word, for example `DOCS: Latest Agents Context Reflection`, `STYLE: Standardize Python Formatting`, or `FEAT: Bootstrap JQAnywhere v0.1 Framework`.
- When creating a commit from `main`, first switch to a new branch generated from the planned commit subject.
- Use lowercase slash-separated branch names: `type/description` when there is no scope, or `type/scope/description` when there is a scope.
- Convert the description to kebab-case for the branch, for example `docs/latest-agents-context-reflection`, `docs/agents/document-commit-standard`, or `feat/bootstrap/bootstrap-jqanywhere-v0.1-framework`.
- Use Markdown for optional commit bodies, separated from the subject by a blank line.
- Use optional footers after the body, separated by a blank line, following git trailer-style formatting.
- Use `FIX` for bug patches and `FEAT` for new features; other conventional types are allowed when they better communicate intent.
- Mark breaking API changes with `!` after the type or scope, or with a `BREAKING CHANGE: <description>` footer.

```text
<TYPE>[optional scope]: <description>

[optional body in Markdown]

[optional footer(s)]
```

## Architecture Notes

- This package is a live-trading/event-driven compatibility runtime, not a backtesting engine or strategy adapter: copied user strategies should keep JoinQuant style, especially `from jqdata import *`, `initialize(context)`, `run_daily(...)`, global `g`, and order functions.
- Preserve the live-first design. JQAnywhere processes one externally triggered scheduled event per invocation, persists state between invocations, and routes orders to the configured paper or live broker. Do not add historical date-range replay, research backtest orchestration, synthetic full-day bar loops, or in-process broker simulation unless the user explicitly requests a separate backtesting product.
- `src/jqdata` is the public compatibility package imported by strategies; most implementation lives under `src/jqanywhere`.
- Main local CLI entrypoint is `jqanywhere.cli:main`; Lambda entrypoint is `jqanywhere.runtime.lambda_handler.run`.
- Runtime construction is centralized in `src/jqanywhere/runtime/factory.py`; it selects `empty`, `adata`, or `remote_miniqmt` data, `paper` or `remote_miniqmt` broker, memory or DynamoDB state, and console or SNS notifier from config/env.
- `RuntimeEngine.run()` loads the strategy file, requires `initialize(context)`, runs due scheduled jobs and lifecycle hooks, persists `g` plus portfolio/order metadata, sends logs, records failed-run metadata, and always resets the runtime session token.
- Supported v0.9.0 compatibility includes daily/weekly/monthly scheduling, safe daily schedule aliases, externally driven `every_bar` minute scheduling, optional `before_trading_start` and `after_trading_end`, `context.current_dt`, `context.previous_date` when a trade calendar is available, `context.run_params.end_date` as a single-event shim, market-data APIs, event-driven paper order APIs with JoinQuant-style `None` on order creation failure, import-compatible unsupported JoinQuant API stubs that fail explicitly, duplicate scheduled-run skipping, stale active-run recovery, and structured `completed`/`skipped`/`failed` results.
- Treat `runtime.mode = "paper"` as live-style paper trading/dry-run execution, not backtesting. Treat `jqanywhere run --now ...` as setting a single event timestamp only; it does not require data providers to replay historical market data.
- `src/jqanywhere/data/adata_provider.py` adapts AData 2.9.x for China stocks, ETFs/LOFs/common exchange-traded fund code families, indexes, convertible-bond metadata, current data, daily/history data, and trade calendars; keep upstream AData limitations explicit. Historical ETF NAV extras are not implemented from latest metadata and should raise on dated requests.
- `run_daily(..., time="every_bar")` is intentionally a minimal v0.9.0 implementation: JQAnywhere runs it only when invoked at an eligible trading minute and does not synthesize an internal 240-bar loop. Use EventBridge/cron per-minute schedules for live-style execution.
- `src/jqanywhere/miniqmt_remote` is only an HTTPS JSON client for a separately deployed MiniQMT agent; do not add in-process `xtquant` runtime assumptions to this repo.

## Config And Deployment Gotchas

- `load_config()` reads `jqanywhere.toml` by default, or `JQANYWHERE_CONFIG`; example config lives at `examples/jqanywhere.toml`.
- Environment overrides include `JQANYWHERE_STRATEGY_PATH`, `JQANYWHERE_STRATEGY_ID`, `JQANYWHERE_TIMEZONE`, `JQANYWHERE_MODE`, `JQANYWHERE_DATA_PROVIDER`, `JQANYWHERE_DATA_STRICT_CURRENT_DATE`, `JQANYWHERE_MINIQMT_ENDPOINT`, `JQANYWHERE_DATA_ENDPOINT`, `JQANYWHERE_DATA_TOKEN_ENV`, `JQANYWHERE_BROKER`, `JQANYWHERE_INITIAL_CASH`, `JQANYWHERE_BROKER_ENDPOINT`, `JQANYWHERE_BROKER_TOKEN_ENV`, `JQANYWHERE_MINIQMT_ACCOUNT_ID`, `JQANYWHERE_MINIQMT_ACCOUNT_TYPE`, `JQANYWHERE_MINIQMT_STRATEGY_NAME`, `JQANYWHERE_ENABLE_LIVE_TRADING`, `JQANYWHERE_PERSISTENCE`, `JQANYWHERE_STATE_TABLE`, `JQANYWHERE_NOTIFIER`, `MAIL_MEOW_BASE_URL`, `MAIL_MEOW_API_KEY`, `NOTIFICATION_EMAIL`, `AWS_ENDPOINT_URL`, and `JQANYWHERE_EVENTBRIDGE_SCHEDULE`.
- `serverless.yml` defaults Lambda runtime to `python3.13` via `LAMBDA_RUNTIME`, architecture to `arm64`, data provider to `adata`, persistence to DynamoDB, notifier to SNS, and reserved concurrency to `1`; notification-specific resources are split under `serverless/notifications/`.
- Serverless Framework v4 bundles Python requirements packaging for this project; do not add `serverless-python-requirements` to `serverless.yml`, `package.json`, or `package-lock.json`.
- Serverless packaging includes `src/**`, `examples/**`, and `jqanywhere.toml`, and excludes `tests/**`, `.venv/**`, and `private/**`.

## Compatibility Constraints

- This is critical financial code. Any API advertised as JoinQuant-compatible must either match JoinQuant behavior exactly for the supported inputs or fail explicitly; never return approximated, fabricated, best-effort, placeholder, or partially compatible financial data.
- Unsupported JoinQuant APIs should fail explicitly with `NotImplementedError` rather than silently doing the wrong thing; this includes `handle_data`, internal tick/minute event loops, historical backtest/research orchestration, unsupported market-data historical paths, fundamentals/query DSL when no provider implements it, finance/macro query APIs, factor APIs, portfolio optimizer, futures, and margin trading. `open`, `close`, `after_close`, and externally driven `every_bar` are supported scheduler aliases.
- Live broker integration is intentionally a template/remote-agent extension point; see `src/jqanywhere/broker/template.py` and `src/jqanywhere/broker/remote_miniqmt.py` before adding broker behavior.
- `remote_miniqmt` broker requires `runtime.mode = "live"`, an endpoint, and `account_id`; keep `enable_trading = false` until the external agent has been validated in read-only mode.
