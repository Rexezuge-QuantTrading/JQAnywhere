"""DynamoDB state store."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from jqanywhere.persistence.base import RunClaim, StateStore


class DynamoDBStateStore(StateStore):
    def __init__(self, table_name: str, endpoint_url: str | None = None):
        import boto3

        self.table = boto3.resource("dynamodb", endpoint_url=endpoint_url or None).Table(table_name)

    def load(self, strategy_id: str) -> dict[str, Any]:
        item = self.table.get_item(Key={"id": strategy_id}).get("Item")
        return _from_dynamodb_value(item.get("state", {})) if item else {}

    def save(self, strategy_id: str, state: dict[str, Any]) -> None:
        self.table.put_item(Item={"id": strategy_id, "state": _to_dynamodb_value(state)})

    def claim_run(self, strategy_id: str, state: dict[str, Any], run_key: str) -> RunClaim:
        from botocore.exceptions import ClientError

        metadata = dict(state.get("metadata", {}))
        if metadata.get("last_run_key") == run_key or metadata.get("active_run_key") == run_key:
            return RunClaim(False, state)
        expected_revision = int(metadata.get("revision", 0))
        metadata["revision"] = expected_revision + 1
        metadata["active_run_key"] = run_key
        metadata["last_status"] = "running"
        next_state = dict(state)
        next_state["metadata"] = metadata
        try:
            self.table.put_item(
                Item={"id": strategy_id, "state": _to_dynamodb_value(next_state)},
                ConditionExpression=(
                    "attribute_not_exists(#id) OR attribute_not_exists(#state.#metadata.#revision) "
                    "OR #state.#metadata.#revision = :revision"
                ),
                ExpressionAttributeNames={"#id": "id", "#state": "state", "#metadata": "metadata", "#revision": "revision"},
                ExpressionAttributeValues={":revision": Decimal(expected_revision)},
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise
            return RunClaim(False, self.load(strategy_id))
        return RunClaim(True, next_state)


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
