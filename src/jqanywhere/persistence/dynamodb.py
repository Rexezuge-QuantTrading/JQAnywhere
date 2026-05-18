"""DynamoDB state store."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from jqanywhere.persistence.base import StateStore


class DynamoDBStateStore(StateStore):
    def __init__(self, table_name: str, endpoint_url: str | None = None):
        import boto3

        self.table = boto3.resource("dynamodb", endpoint_url=endpoint_url or None).Table(table_name)

    def load(self, strategy_id: str) -> dict[str, Any]:
        item = self.table.get_item(Key={"id": strategy_id}).get("Item")
        return _from_dynamodb_value(item.get("state", {})) if item else {}

    def save(self, strategy_id: str, state: dict[str, Any]) -> None:
        self.table.put_item(Item={"id": strategy_id, "state": _to_dynamodb_value(state)})


def _to_dynamodb_value(value):
    if isinstance(value, dict):
        return {key: _to_dynamodb_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_dynamodb_value(item) for item in value]
    if isinstance(value, tuple):
        return [_to_dynamodb_value(item) for item in value]
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    return value


def _from_dynamodb_value(value):
    if isinstance(value, dict):
        return {key: _from_dynamodb_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_from_dynamodb_value(item) for item in value]
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value
