JQAnywhere
==========

JQAnywhere is an MIT-licensed live-trading runtime for running JoinQuant-style strategies on AWS-compatible infrastructure. The goal is to let users copy a supported JoinQuant strategy file unchanged, keep `from jqdata import *`, and run it locally, on AWS, or on an AWS-compatible emulator as an event-driven paper or live trading process.

Status: v0.9.0 alpha.

JQAnywhere is designed for live trading, not backtesting. It processes one externally triggered scheduled event at a time, persists state between invocations, and sends orders to the configured paper or live broker. It does not replay historical date ranges, synthesize full intraday bar loops, or provide a portfolio simulator for research/backtest performance analysis.

This is critical financial software. Any API described as JoinQuant-compatible must either match JoinQuant behavior for the supported inputs or fail explicitly with an exception. JQAnywhere does not return fabricated, placeholder, best-effort, or partially compatible financial data.

Legal Notice
------------

JQAnywhere is an independent MIT-licensed open-source project. It is not affiliated with, endorsed by, or connected to JoinQuant (聚宽).

The project provides an independently implemented runtime that aims to support publicly observable JoinQuant-style strategy APIs. No JoinQuant source code, documentation text, proprietary datasets, or internal implementation details are used.

"JQ" in the project name refers only to "JoinQuant-style API compatibility" and does not imply any official relationship.

Live-First Scope
----------------

- `runtime.mode = "paper"` means event-driven paper trading/dry-run execution against the configured data provider; it is not a historical backtest mode.
- `runtime.mode = "live"` is required for live broker adapters such as `remote_miniqmt`.
- `jqanywhere run --now ...` sets the event timestamp for one invocation. It is useful for deterministic scheduling checks and local operations, but data providers may still use current/latest upstream data and it should not be treated as historical replay.
- `run_daily(..., time="every_bar")` only runs when JQAnywhere is invoked for an eligible trading minute; use EventBridge or cron per-minute schedules for live-style minute execution.

Quick Start
-----------

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/jqanywhere run --config examples/jqanywhere.toml --now 2026-05-18T09:50:00+08:00
```

The CLI can also validate config and print the supported compatibility surface:

```bash
.venv/bin/jqanywhere config validate --config examples/jqanywhere.toml
.venv/bin/jqanywhere list-api
```

The example is intentionally small and public:

```python
from jqdata import *


def initialize(context):
    set_option("use_real_price", True)
    set_benchmark("000300.XSHG")
    run_daily(trade, "09:50")


def trade(context):
    order_target_value("000300.XSHG", context.portfolio.total_value)
```

Design
------

JQAnywhere is a live/event-driven compatibility runtime, not a strategy-adapter framework or backtesting engine. User strategy files should stay in JoinQuant's global-function style:

- `from jqdata import *`
- `initialize(context)`
- `run_daily(func, "09:50")`
- strategy state stored on `g`
- orders sent through JoinQuant-style functions such as `order_target_value`
- technical indicators imported from the full `talib` package

Internally, JQAnywhere separates runtime concerns:

- `jqdata`: compatibility package imported by copied JoinQuant strategies
- `jqanywhere.runtime`: strategy loading, runtime session, scheduling, Lambda handler
- `jqanywhere.data`: market data provider interface, empty provider, AData adapter, remote MiniQMT adapter
- `jqanywhere.broker`: swappable broker interface, paper broker, remote MiniQMT broker, live broker template
- `jqanywhere.persistence`: state stores such as memory and DynamoDB
- `jqanywhere.notifications`: console, SNS, and MailMeow notifications

Supported In v0.9.0
-------------------

- `initialize(context)`
- time-aware `run_daily(func, "HH:MM", reference_security="")`
- `run_daily(func, "every_bar", reference_security="")` when JQAnywhere is invoked externally once per trading minute
- deterministic `run_daily` schedule aliases: `before_open`, `open`, `close`, and `after_close`
- calendar-aware `run_weekly(func, weekday, "HH:MM", reference_security="")`
- calendar-aware `run_monthly(func, monthday, "HH:MM", reference_security="")`
- optional `before_trading_start(context)` and `after_trading_end(context)` lifecycle hooks around due jobs
- `g`, `context`, `log`
- `context.current_dt`
- `context.previous_date` when the selected data provider exposes a trade calendar
- `context.run_params.type` as a JoinQuant compatibility shim; the current value is not a JQAnywhere backtest mode
- `context.run_params.end_date` as a v0.9.0 single-event compatibility shim; this is not a full JoinQuant backtest range
- `context.run_params.frequency`
- `set_option`
- `set_benchmark`
- `set_slippage`
- `set_order_cost`
- `set_commission`
- `set_universe`
- `disable_cache` as a safe no-op because JQAnywhere does not keep a JoinQuant data cache
- `set_subportfolios` for stock/fund-style subaccounts
- `SubPortfolioConfig`
- `context.subportfolios`
- `attribute_history`
- `history`
- `get_current_data`
- `get_price`
- `get_bars` where the configured data provider supports exact bar data
- `get_money_flow` where the configured data provider supports the requested fields
- `get_index_stocks`
- `get_all_securities`
- `get_security_info`
- `get_trade_days`
- `get_all_trade_days`
- import-compatible fundamentals query objects: `query`, `valuation`, `balance`, `cash_flow`, `income`, and `indicator`
- `get_fundamentals` where the configured data provider supports fundamentals
- `get_valuation` where the configured data provider supports valuation data
- `get_industry` where the configured data provider supports industry data
- `get_industries` where the configured data provider supports industry lists
- `get_industry_stocks` where the configured data provider supports industry constituents
- `get_extras` where the configured data provider supports extras such as ETF unit net value
- `finance.run_query` where the configured data provider supports exact finance tables
- `record`
- `order`
- `order_target`
- `order_value`
- `order_target_value`
- `cancel_order`
- `get_open_orders`
- `get_orders`
- event-driven paper-trading portfolio accounting with market-data-based fills, fixed or price-related slippage, configured commission/order cost, rejection reasons, T+1-style closeable amounts, and order history
- `pindex`-aware paper order routing across configured subportfolios
- persisted paper portfolio cash, subportfolio cash, positions, subaccount types, and order history
- persisted order history and failed-run metadata
- duplicate scheduled-run skipping for repeated EventBridge timestamps
- scheduled-run claiming for state stores, including DynamoDB conditional claims to reduce concurrent duplicate execution risk
- structured run results with `completed`, `skipped`, and `failed` statuses
- failure notifications through configured notifiers
- strict provider validation for config and environment overrides
- in-memory state store
- DynamoDB state store
- console notifications
- SNS notifications
- MailMeow notifications
- AWS Lambda entrypoint
- EventBridge event-time handling
- Serverless deployment template
- deterministic local event invocation through `jqanywhere run --now ...`
- machine-readable CLI output through `jqanywhere run --json ...`
- direct one-off strategy invocation through `jqanywhere invoke --strategy ...`
- config validation through `jqanywhere config validate --config ...`
- operational config/provider checks through `jqanywhere doctor --config ...`
- API surface inspection through `jqanywhere list-api`
- full `talib` package imports for copied strategies
- import-compatible official JoinQuant API stubs for unsupported APIs that fail explicitly when called
- import-compatible `jqfactor` package stubs for factor APIs that still fail explicitly when called
- AWS-compatible emulator endpoint support through `AWS_ENDPOINT_URL`

AData Provider
--------------

Set `[data].provider = "adata"` or `JQANYWHERE_DATA_PROVIDER=adata` to use AData-backed China market data. The v0.9.0 adapter maps JoinQuant-style APIs to the real `adata 2.9.x` SDK surface:

- stocks: daily prices, current quotes, code metadata, and latest-day minute data where AData exposes it
- ETFs, LOFs, and common exchange-traded fund code families: daily prices, latest-day minute data, current quotes, and ETF metadata where upstream AData exposes them
- indexes: daily prices, latest-day minute data, current quotes, index metadata, and index constituents
- convertible bonds: metadata through `get_all_securities(types="bond")`
- trade calendars through `get_trade_days` and `get_all_trade_days`
- Shenwan industry metadata through `get_industry` when the installed AData SDK exposes it
- latest ETF net-value extras through `get_extras("unit_net_value", ...)`, `get_extras("acc_net_value", ...)`, and `get_extras("adj_net_value", ...)` where the installed AData SDK exposes those fields
- `get_money_flow(..., fields=["date", "sec_code", "change_pct"])` from provider-backed price changes
- `get_bars(..., df=True/False)` for bars backed by the same price endpoints as `get_price`

Known AData-backed limits:

- historical minute data is only supported where the upstream AData endpoint exposes it; stock, ETF, and index minute endpoints are latest-trading-day oriented
- historical ETF net-value extras are not implemented from AData latest metadata; dated requests fail explicitly rather than silently introducing lookahead
- JoinQuant fundamentals/query DSL, `get_valuation`, and `finance.run_query` are import-compatible but not implemented from AData because AData does not expose exact JoinQuant tables and field semantics
- unsupported `get_money_flow` fields fail explicitly instead of returning incomplete capital-flow data
- `fq="pre"` is the safest stock adjustment mode; other adjustment modes depend on upstream AData behavior

Unsupported In v0.9.0
---------------------

These APIs are deliberately unsupported and should raise explicit `NotImplementedError` errors instead of silently doing the wrong thing:

- `handle_data`
- internal tick/minute event loops; v0.9.0 `every_bar` support depends on external per-minute invocations and does not synthesize all intraday bars inside one run
- tick data APIs such as `get_current_tick` and `get_ticks`
- `get_trades` until trade history is backed by exact broker/provider records
- concept, billboard, locked-shares, call-auction, and other data APIs without exact provider backing
- research/backtest orchestration APIs such as `create_backtest`
- file, message, subscription, and profiling APIs
- fundamentals/query execution when the selected provider does not implement fundamentals
- `finance.run_query` when the selected provider does not implement exact finance tables
- `macro.run_query`
- factor APIs beyond import-compatible `jqfactor` stubs
- portfolio optimizer
- margin trading
- futures
- direct in-process `xtquant` broker integration

Remote MiniQMT Agent
--------------------

JQAnywhere can talk to a separately deployed MiniQMT HTTP agent through `remote_miniqmt` providers. The MiniQMT client and `xtquant` runtime stay outside this repository; JQAnywhere only sees an HTTPS JSON API.

Minimal read-only live config:

```toml
[runtime]
mode = "live"

[data]
provider = "remote_miniqmt"
endpoint = "https://miniqmt-agent.local:8443"

[broker]
provider = "remote_miniqmt"
endpoint = "https://miniqmt-agent.local:8443"
account_id = "1000000365"
account_type = "STOCK"
enable_trading = false
```

Set `enable_trading = true` only after validating the external agent, account mapping, network security, and idempotent order handling. `JQANYWHERE_MINIQMT_ENDPOINT` can provide one endpoint for both data and broker providers; `JQANYWHERE_DATA_ENDPOINT` and `JQANYWHERE_BROKER_ENDPOINT` override them independently when needed.

Security notes:

- put the agent on a private network such as Tailscale or WireGuard
- set `MINIQMT_AGENT_TOKEN` and configure HTTPS or mTLS for non-localhost traffic
- keep `enable_trading = false` until the agent has been validated in read-only mode
- the agent is the live account source of truth; JQAnywhere syncs portfolio state before each scheduled run

Operational Notes
-----------------

- `jqanywhere run --json` writes the single-event run result as JSON on stdout; console notifications are written to stderr.
- `jqanywhere invoke --strategy path/to/file.py` processes a strategy file for one event while still loading provider, broker, persistence, and notification settings from config/env.
- `--now` controls the invocation timestamp only; it does not switch providers into historical replay or backtest mode.
- Repeated scheduled invocations at the same normalized event minute are skipped after a successful run, preventing duplicate order execution for at-least-once EventBridge delivery.
- Scheduled runs first claim the normalized event minute in the configured state store; DynamoDB uses a conditional claim to reduce duplicate execution under concurrent delivery.
- Runtime failures return `status="failed"` and send a failure notification containing the strategy id, event time, and exception summary.
- Runtime failures persist `last_status="failed"`, `last_failed_at`, and `last_error`; failed scheduled runs are retryable because they do not advance `last_run_key`.
- Unknown providers such as `[data].provider = "bad"` fail during config loading instead of silently falling back to defaults.
- Paper trading is deterministic event-driven execution, not a JoinQuant backtest simulator or full live broker simulator. Market orders require provider-backed current data or recent close, apply configured fixed slippage and cost settings, and reject missing-price, paused, or limit-blocked securities.
- Paper order creation failures return `None` to strategies, matching JoinQuant-style failure checks, while rejected order details remain in returned run history for diagnostics.
- Paper portfolios mark persisted positions to available current or recent prices before each run so local account value reflects price movement between scheduled invocations.

Broker Integration
------------------

Live trading is designed as a remote-agent/template model. Strategies call JoinQuant-style functions, while users either configure `remote_miniqmt` or swap the broker implementation:

```python
from jqanywhere.broker.base import Broker


class MyBroker(Broker):
    def order_target_value(self, context, security, value, **kwargs):
        # Translate symbol, sync account state, submit order, enforce idempotency.
        ...
```

See `src/jqanywhere/broker/template.py` for the intended extension point.

Serverless
----------

The repository includes `serverless.yml` with:

- Lambda handler: `src/jqanywhere/runtime/lambda_handler.run` for the packaged `src/**` layout
- EventBridge schedule
- Serverless Framework v4 Python requirements packaging for pandas, numpy, adata, TA-Lib, and other Python dependencies
- CI-generated `requirements.txt` from `pyproject.toml` for Lambda dependency packaging
- reserved Lambda concurrency defaulting to `1` to reduce overlapping scheduled runs
- CloudWatch log retention through `LOG_RETENTION_DAYS`
- DynamoDB state table
- provider-specific notification resources under `serverless/notifications/`
- SNS topic when `JQANYWHERE_NOTIFIER=sns`
- Floci-compatible local AWS emulator deployment through Serverless local-stage endpoint configuration
- package exclusions for `.venv`, `tests`, and `private` by default

Set `JQANYWHERE_NOTIFIER` to `sns`, `console`, or `mailmeow` to select the Serverless notification fragment. `mailmeow` requires `MAIL_MEOW_BASE_URL`, `MAIL_MEOW_API_KEY`, and `NOTIFICATION_EMAIL`; missing values fail explicitly during config loading.

GitHub Actions runs a Serverless smoke test against [Floci](https://github.com/floci-io/floci): it starts `floci/floci`, deploys the stack with Serverless Framework v4, verifies the Lambda/DynamoDB/SNS resources, and invokes the deployed `runner` Lambda. The workflow expects `SERVERLESS_LICENSE_KEY` to be configured as a GitHub secret for Serverless v4. `JQANYWHERE_AWS_ENDPOINT_URL` can override the `AWS_ENDPOINT_URL` injected into Lambda while host-side tools still use `AWS_ENDPOINT_URL`.

Useful environment variables:

- `JQANYWHERE_CONFIG`
- `JQANYWHERE_STRATEGY_PATH`
- `JQANYWHERE_STRATEGY_ID`
- `JQANYWHERE_TIMEZONE`
- `JQANYWHERE_MODE`
- `JQANYWHERE_DATA_PROVIDER`
- `JQANYWHERE_DATA_STRICT_CURRENT_DATE`
- `JQANYWHERE_MINIQMT_ENDPOINT`
- `JQANYWHERE_DATA_ENDPOINT`
- `JQANYWHERE_DATA_TOKEN_ENV`
- `JQANYWHERE_DATA_TIMEOUT_SECONDS`
- `JQANYWHERE_BROKER`
- `JQANYWHERE_INITIAL_CASH`
- `JQANYWHERE_BROKER_ENDPOINT`
- `JQANYWHERE_BROKER_TOKEN_ENV`
- `JQANYWHERE_BROKER_TIMEOUT_SECONDS`
- `JQANYWHERE_MINIQMT_ACCOUNT_ID`
- `JQANYWHERE_MINIQMT_ACCOUNT_TYPE`
- `JQANYWHERE_MINIQMT_STRATEGY_NAME`
- `JQANYWHERE_ENABLE_LIVE_TRADING`
- `JQANYWHERE_PERSISTENCE`
- `JQANYWHERE_STATE_TABLE`
- `JQANYWHERE_NOTIFIER`
- `MAIL_MEOW_BASE_URL`
- `MAIL_MEOW_API_KEY`
- `NOTIFICATION_EMAIL`
- `AWS_ENDPOINT_URL`
- `JQANYWHERE_AWS_ENDPOINT_URL` (Serverless-only Lambda endpoint override)
- `JQANYWHERE_EVENTBRIDGE_SCHEDULE`

License
-------

MIT.
