from datetime import datetime

from jqanywhere.broker.remote_miniqmt import RemoteMiniQmtBroker
from jqanywhere.data.remote_miniqmt import RemoteMiniQmtMarketDataProvider
from jqanywhere.jqcompat.types import Context, OrderStatus, Portfolio


class FakeMiniQmtClient:
    def __init__(self):
        self.requests = []

    def get(self, path, query=None):
        self.requests.append(("GET", path, query))
        if path == "/v1/accounts/1000000365/portfolio":
            return {
                "available_cash": 1234.5,
                "positions": [
                    {
                        "security": "000001.XSHE",
                        "total_amount": 200,
                        "closeable_amount": 100,
                        "price": 10.0,
                        "avg_cost": 9.5,
                        "value": 2000.0,
                    }
                ],
            }
        raise AssertionError(path)

    def post(self, path, payload):
        self.requests.append(("POST", path, payload))
        if path == "/v1/market/history":
            return {"rows": [{"datetime": "2026-05-15", "open": 9.0, "close": 10.0}]}
        if path == "/v1/market/current":
            return {"current": [{"security": "000001.XSHE", "last_price": 10.1, "high_limit": 11.0, "low_limit": 9.0}]}
        if path == "/v1/orders":
            return {
                "client_order_id": payload["client_order_id"],
                "broker_order_id": "42",
                "security": payload["security"],
                "amount": 100,
                "filled_amount": 0,
                "price": 10.0,
                "value": 1000.0,
                "status": "submitted",
            }
        raise AssertionError(path)


def test_remote_miniqmt_data_provider_maps_history_and_current_data():
    provider = RemoteMiniQmtMarketDataProvider(FakeMiniQmtClient())

    history = provider.attribute_history("000001.XSHE", 1, "1d", ["open", "close"], True, True, "pre")
    current = provider.get_current_data()["000001.XSHE"]

    assert history["close"].iloc[0] == 10.0
    assert current.last_price == 10.1
    assert current.high_limit == 11.0


def test_remote_miniqmt_broker_syncs_portfolio_and_submits_idempotent_order():
    client = FakeMiniQmtClient()
    broker = RemoteMiniQmtBroker(client, "1000000365", enable_trading=True)
    context = Context(portfolio=Portfolio(100_000, 100_000), current_dt=datetime(2026, 5, 18, 9, 50))

    broker.sync_portfolio(context)
    order = broker.order_target_value(context, "000001.XSHE", 1000)

    assert context.portfolio.available_cash == 1234.5
    assert context.portfolio.positions["000001.XSHE"].total_amount == 200
    assert order.status is OrderStatus.open
    assert context.order_history[0]["status"] == "open"
    assert context.order_history[0]["client_order_id"].startswith("jq")
    assert client.requests[-1][2]["method"] == "order_target_value"


def test_remote_miniqmt_broker_reuses_client_order_id_for_same_run_target():
    client = FakeMiniQmtClient()
    broker = RemoteMiniQmtBroker(client, "1000000365", enable_trading=True)
    context = Context(portfolio=Portfolio(100_000, 100_000), current_dt=datetime(2026, 5, 18, 9, 50))

    first = broker.order_target_value(context, "000001.XSHE", 1000)
    second = broker.order_target_value(context, "000001.XSHE", 1000)

    order_posts = [request for request in client.requests if request[1] == "/v1/orders"]
    assert first.status == second.status
    assert order_posts[0][2]["client_order_id"] == order_posts[1][2]["client_order_id"]
