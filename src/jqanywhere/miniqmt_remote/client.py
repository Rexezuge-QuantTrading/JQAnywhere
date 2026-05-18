"""HTTP client for the remote MiniQMT agent protocol."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class MiniQmtHttpError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status = status
        self.payload = payload


class MiniQmtHttpClient:
    def __init__(self, endpoint: str, token: str | None = None, timeout: float = 10.0):
        self.endpoint = endpoint.rstrip("/")
        self.token = token
        self.timeout = timeout

    def get(self, path: str, query: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("GET", path, query=query)

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, payload=payload)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.endpoint}{path}"
        if query:
            url = f"{url}?{urlencode({key: value for key, value in query.items() if value is not None})}"
        body = None if payload is None else json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:  # noqa: S310 - endpoint is user-configured for this client.
                raw = response.read()
        except HTTPError as exc:
            payload = _decode_error_payload(exc)
            message = payload.get("detail") if isinstance(payload, dict) else None
            raise MiniQmtHttpError(message or f"MiniQMT agent returned HTTP {exc.code}", status=exc.code, payload=payload) from exc
        except URLError as exc:
            raise MiniQmtHttpError(f"MiniQMT agent request failed: {exc.reason}") from exc
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))


def _decode_error_payload(exc: HTTPError):
    try:
        raw = exc.read()
    except Exception:
        return None
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return raw.decode("utf-8", errors="replace")
