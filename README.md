JQAnywhere
==========

JQAnywhere is an MIT-licensed Python framework for running JoinQuant-style strategies on AWS-compatible infrastructure. The goal is to let users copy a supported JoinQuant strategy file unchanged, keep `from jqdata import *`, and run it locally, on AWS, or on LocalStack.

Status: v0.6 alpha.

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

JQAnywhere is a compatibility runtime, not a strategy-adapter framework. User strategy files should stay in JoinQuant's global-function style:

- `from jqdata import *`
- `initialize(context)`
- `run_daily(func, "09:50")`
- strategy state stored on `g`
- orders sent through JoinQuant-style functions such as `order_target_value`

Internally, JQAnywhere separates runtime concerns:

- `jqdata`: compatibility package imported by copied JoinQuant strategies
- `jqanywhere.runtime`: strategy loading, runtime session, scheduling, Lambda handler
- `jqanywhere.data`: market data provider interface, empty provider, AData adapter, remote MiniQMT adapter
- `jqanywhere.broker`: swappable broker interface, paper broker, remote MiniQMT broker, live broker template
- `jqanywhere.persistence`: state stores such as memory and DynamoDB
- `jqanywhere.notifications`: console and SNS notifications

Supported In v0.6
-----------------

- `initialize(context)`
- time-aware `run_daily(func, "HH:MM", reference_security="")`
- deterministic `run_daily` schedule aliases: `before_open`, `open`, `close`, and `after_close`
- calendar-aware `run_weekly(func, weekday, "HH:MM", reference_security="")`
- calendar-aware `run_monthly(func, monthday, "HH:MM", reference_security="")`
- optional `before_trading_start(context)` and `after_trading_end(context)` lifecycle hooks around due jobs
- `g`, `context`, `log`
- `context.current_dt`
- `context.previous_date` when the selected data provider exposes a trade calendar
- `set_option`
- `set_benchmark`
- `set_slippage`
- `set_order_cost`
- `set_commission`
- `attribute_history`
- `get_current_data`
- `get_price`
- `get_index_stocks`
- `get_all_securities`
- `get_security_info`
- `get_trade_days`
- `get_all_trade_days`
- `order`
- `order_target`
- `order_value`
- `order_target_value`
- paper portfolio accounting with market-data-based fills, fixed slippage, configured commission/order cost, rejection reasons, and order history
- persisted paper portfolio cash and positions
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
- AWS Lambda entrypoint
- EventBridge event-time handling
- Serverless deployment template
- deterministic local invocation through `jqanywhere run --now ...`
- machine-readable CLI output through `jqanywhere run --json ...`
- direct one-off strategy invocation through `jqanywhere invoke --strategy ...`
- config validation through `jqanywhere config validate --config ...`
- operational config/provider checks through `jqanywhere doctor --config ...`
- API surface inspection through `jqanywhere list-api`
- LocalStack endpoint support through `AWS_ENDPOINT_URL`

AData Provider
--------------

Set `[data].provider = "adata"` or `JQANYWHERE_DATA_PROVIDER=adata` to use AData-backed China market data. The v0.6 adapter maps JoinQuant-style APIs to the real `adata 2.9.x` SDK surface:

- stocks: daily prices, current quotes, code metadata, and latest-day minute data where AData exposes it
- ETFs: daily prices, latest-day minute data, current quotes, and ETF metadata
- indexes: daily prices, latest-day minute data, current quotes, index metadata, and index constituents
- convertible bonds: metadata through `get_all_securities(types="bond")`
- trade calendars through `get_trade_days` and `get_all_trade_days`

Known AData-backed limits:

- historical minute data is only supported where the upstream AData endpoint exposes it; stock, ETF, and index minute endpoints are latest-trading-day oriented
- JoinQuant fundamentals/query DSL is not implemented from AData finance data because AData only exposes selected core financial indicators
- `fq="pre"` is the safest stock adjustment mode; other adjustment modes depend on upstream AData behavior

Unsupported In v0.6
-------------------

These APIs are deliberately unsupported and should raise explicit `NotImplementedError` errors instead of silently doing the wrong thing:

- `handle_data`
- tick/minute event loop
- tick/minute event-loop schedule alias `every_bar`
- fundamentals/query DSL: `query`, `valuation`, `balance`, `cash_flow`, `income`, `indicator`
- `get_fundamentals`
- `finance.run_query`
- `macro.run_query`
- factor APIs
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

- `jqanywhere run --json` writes the run result as JSON on stdout; console notifications are written to stderr.
- `jqanywhere invoke --strategy path/to/file.py` runs a strategy file once while still loading provider, broker, persistence, and notification settings from config/env.
- Repeated scheduled invocations at the same normalized event minute are skipped after a successful run, preventing duplicate order execution for at-least-once EventBridge delivery.
- Scheduled runs first claim the normalized event minute in the configured state store; DynamoDB uses a conditional claim to reduce duplicate execution under concurrent delivery.
- Runtime failures return `status="failed"` and send a failure notification containing the strategy id, event time, and exception summary.
- Runtime failures persist `last_status="failed"`, `last_failed_at`, and `last_error`; failed scheduled runs are retryable because they do not advance `last_run_key`.
- Unknown providers such as `[data].provider = "bad"` fail during config loading instead of silently falling back to defaults.
- Paper trading is still a deterministic approximation. Market orders use current data or recent close when available, apply configured fixed slippage and cost settings, and reject paused or limit-blocked securities, but it is not a live broker simulator.
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
- Serverless Framework v4 Python requirements packaging for pandas, numpy, adata, and other Python dependencies
- reserved Lambda concurrency defaulting to `1` to reduce overlapping scheduled runs
- CloudWatch log retention through `LOG_RETENTION_DAYS`
- DynamoDB state table
- SNS topic
- Floci-compatible local AWS emulator deployment through the `serverless-localstack` endpoint plugin
- package exclusions for `.venv`, `tests`, and `private` by default

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
- `AWS_ENDPOINT_URL`
- `JQANYWHERE_AWS_ENDPOINT_URL` (Serverless-only Lambda endpoint override)
- `JQANYWHERE_EVENTBRIDGE_SCHEDULE`

License
-------

MIT.
