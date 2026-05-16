"""DynamoDB state store."""

from __future__ import annotations

from typing import Any

from jqanywhere.persistence.base import StateStore


class DynamoDBStateStore(StateStore):
    def __init__(self, table_name: str, endpoint_url: str | None = None):
        import boto3

        self.table = boto3.resource("dynamodb", endpoint_url=endpoint_url or None).Table(table_name)

    def load(self, strategy_id: str) -> dict[str, Any]:
        item = self.table.get_item(Key={"id": strategy_id}).get("Item")
        return item.get("state", {}) if item else {}

    def save(self, strategy_id: str, state: dict[str, Any]) -> None:
        self.table.put_item(Item={"id": strategy_id, "state": state})
