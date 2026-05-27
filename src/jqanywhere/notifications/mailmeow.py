"""MailMeow notifier."""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from jqanywhere.notifications.base import Notifier


class MailMeowNotifier(Notifier):
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        to: str | None = None,
        timeout_seconds: float = 10.0,
    ):
        self.base_url = (base_url if base_url is not None else os.getenv("MAIL_MEOW_BASE_URL", "")).rstrip("/")
        self.api_key = api_key if api_key is not None else os.getenv("MAIL_MEOW_API_KEY", "")
        self.to = to if to is not None else os.getenv("NOTIFICATION_EMAIL", "")
        self.timeout_seconds = timeout_seconds

        missing = []
        if not self.base_url:
            missing.append("MAIL_MEOW_BASE_URL")
        if not self.api_key:
            missing.append("MAIL_MEOW_API_KEY")
        if not self.to:
            missing.append("NOTIFICATION_EMAIL")
        if missing:
            raise ValueError(f"MailMeow notifier requires {', '.join(missing)}")

    def send(self, subject: str, message: str) -> None:
        url = f"{self.base_url}/api/{quote(self.api_key, safe='')}/email"
        payload = json.dumps(
            {
                "to": self.to,
                "subject": subject,
                "text": message or "completed",
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            url,
            data=payload,
            headers={"Accept": "*/*", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310 - endpoint is user-configured.
                status = getattr(response, "status", getattr(response, "code", 200))
                if status < 200 or status >= 300:
                    reason = getattr(response, "reason", "")
                    raise RuntimeError(f"MailMeow returned HTTP {status}: {reason}".rstrip())
        except HTTPError as exc:
            raise RuntimeError(f"MailMeow returned HTTP {exc.code}: {exc.reason}") from exc
        except URLError as exc:
            raise RuntimeError(f"MailMeow request failed: {exc.reason}") from exc
