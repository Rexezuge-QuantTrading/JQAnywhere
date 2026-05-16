JQAnywhere
==========

JQAnywhere is an MIT-licensed Python framework for running JoinQuant-style strategies on AWS-compatible infrastructure. The goal is to let users copy a supported JoinQuant strategy file unchanged, keep `from jqdata import *`, and run it locally, on AWS, or on LocalStack.

Status: v0.1 alpha.

Quick Start
-----------

```bash
pip install -e ".[dev]"
jqanywhere run --config examples/jqanywhere.toml
```

The v0.1 example is intentionally small and public:

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
- `jqanywhere.data`: market data provider interface
- `jqanywhere.broker`: swappable broker interface, paper broker, live broker template
- `jqanywhere.persistence`: state stores such as memory and DynamoDB
- `jqanywhere.notifications`: console and SNS notifications

Supported In v0.1
-----------------

- `initialize(context)`
- `run_daily(func, time, reference_security="")`
- `g`, `context`, `log`
- `set_option`
- `set_benchmark`
- `set_slippage`
- `set_order_cost`
- `set_commission`
- `attribute_history`
- `get_current_data`
- `order`
- `order_target`
- `order_value`
- `order_target_value`
- paper portfolio accounting
- in-memory state store
- DynamoDB state store
- console notifications
- SNS notifications
- AWS Lambda entrypoint
- Serverless deployment template
- LocalStack endpoint support through `AWS_ENDPOINT_URL`

Unsupported In v0.1
-------------------

These APIs are deliberately unsupported and should raise explicit `NotImplementedError` errors instead of silently doing the wrong thing:

- `handle_data`
- tick/minute event loop
- `before_trading_start`
- `after_trading_end`
- fundamentals/query DSL: `query`, `valuation`, `balance`, `cash_flow`, `income`, `indicator`
- `get_fundamentals`
- `finance.run_query`
- `macro.run_query`
- factor APIs
- portfolio optimizer
- margin trading
- futures
- built-in live broker integration

Broker Integration
------------------

Live trading is designed as a template model. Strategies call JoinQuant-style functions, while users swap the broker implementation:

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

- Lambda handler: `jqanywhere.runtime.lambda_handler.run`
- EventBridge schedule
- DynamoDB state table
- SNS topic
- LocalStack plugin configuration

Useful environment variables:

- `JQANYWHERE_CONFIG`
- `JQANYWHERE_STRATEGY_PATH`
- `JQANYWHERE_STRATEGY_ID`
- `JQANYWHERE_INITIAL_CASH`
- `JQANYWHERE_PERSISTENCE`
- `JQANYWHERE_STATE_TABLE`
- `JQANYWHERE_NOTIFIER`
- `AWS_ENDPOINT_URL`

License
-------

MIT.
