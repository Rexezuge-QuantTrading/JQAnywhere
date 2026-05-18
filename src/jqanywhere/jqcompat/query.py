"""Minimal JoinQuant-style fundamentals query DSL."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


class _Evaluable:
    def evaluate(self, data: pd.DataFrame):
        raise NotImplementedError

    def asc(self) -> SortKey:
        return SortKey(self, ascending=True)

    def desc(self) -> SortKey:
        return SortKey(self, ascending=False)

    def _binary(self, other, func: Callable, symbol: str) -> QueryExpression:
        return QueryExpression(lambda data: func(self.evaluate(data), _value(other, data)), f"({self} {symbol} {other})")

    def __add__(self, other) -> QueryExpression:
        return self._binary(other, lambda left, right: left + right, "+")

    def __sub__(self, other) -> QueryExpression:
        return self._binary(other, lambda left, right: left - right, "-")

    def __mul__(self, other) -> QueryExpression:
        return self._binary(other, lambda left, right: left * right, "*")

    def __truediv__(self, other) -> QueryExpression:
        return self._binary(other, lambda left, right: left / right, "/")

    def __gt__(self, other) -> QueryExpression:
        return self._binary(other, lambda left, right: left > right, ">")

    def __ge__(self, other) -> QueryExpression:
        return self._binary(other, lambda left, right: left >= right, ">=")

    def __lt__(self, other) -> QueryExpression:
        return self._binary(other, lambda left, right: left < right, "<")

    def __le__(self, other) -> QueryExpression:
        return self._binary(other, lambda left, right: left <= right, "<=")

    def __eq__(self, other) -> QueryExpression:  # type: ignore[override]
        return self._binary(other, lambda left, right: left == right, "==")

    def __ne__(self, other) -> QueryExpression:  # type: ignore[override]
        return self._binary(other, lambda left, right: left != right, "!=")


@dataclass(frozen=True)
class QueryField(_Evaluable):
    table: str
    name: str

    @property
    def full_name(self) -> str:
        return f"{self.table}.{self.name}"

    def evaluate(self, data: pd.DataFrame):
        if self.name in data.columns:
            return data[self.name]
        if self.full_name in data.columns:
            return data[self.full_name]
        if self.name == "code" and data.index.name == "code":
            return data.index.to_series(index=data.index)
        return pd.Series(pd.NA, index=data.index)

    def in_(self, values) -> QueryExpression:
        return QueryExpression(lambda data: self.evaluate(data).isin(list(values)), f"{self}.in_(...)")

    def between(self, left, right) -> QueryExpression:
        return QueryExpression(lambda data: self.evaluate(data).between(left, right), f"{self}.between({left}, {right})")

    def __str__(self) -> str:
        return self.full_name


class QueryExpression(_Evaluable):
    def __init__(self, evaluator: Callable[[pd.DataFrame], Any], label: str):
        self._evaluator = evaluator
        self.label = label

    def evaluate(self, data: pd.DataFrame):
        return self._evaluator(data)

    def __str__(self) -> str:
        return self.label


@dataclass(frozen=True)
class SortKey:
    expression: _Evaluable
    ascending: bool = True


@dataclass
class FundamentalsQuery:
    fields: tuple[Any, ...] = ()
    conditions: list[QueryExpression] = field(default_factory=list)
    sort_keys: list[SortKey] = field(default_factory=list)
    limit_count: int | None = None

    def filter(self, *conditions) -> FundamentalsQuery:
        self.conditions.extend(condition for condition in conditions if condition is not None)
        return self

    def order_by(self, *keys) -> FundamentalsQuery:
        self.sort_keys.extend(key if isinstance(key, SortKey) else SortKey(key) for key in keys)
        return self

    def limit(self, count: int) -> FundamentalsQuery:
        if not isinstance(count, int) or count < 0:
            raise ValueError("query limit must be a non-negative integer")
        self.limit_count = count
        return self


class QueryTable:
    def __init__(self, name: str):
        self.name = name

    def __getattr__(self, name: str) -> QueryField:
        return QueryField(self.name, name)


def query(*fields) -> FundamentalsQuery:
    return FundamentalsQuery(tuple(fields))


def _value(value, data: pd.DataFrame):
    return value.evaluate(data) if isinstance(value, _Evaluable) else value


valuation = QueryTable("valuation")
balance = QueryTable("balance")
cash_flow = QueryTable("cash_flow")
income = QueryTable("income")
indicator = QueryTable("indicator")


__all__ = [
    "FundamentalsQuery",
    "QueryExpression",
    "QueryField",
    "QueryTable",
    "SortKey",
    "balance",
    "cash_flow",
    "income",
    "indicator",
    "query",
    "valuation",
]
