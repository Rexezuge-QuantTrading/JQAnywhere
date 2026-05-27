import json

import pytest

from jqanywhere.config import load_config
from jqanywhere.notifications.mailmeow import MailMeowNotifier
from jqanywhere.runtime.factory import build_engine


class FakeResponse:
    status = 200
    reason = "OK"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def test_config_accepts_mailmeow_notifier(tmp_path, monkeypatch):
    monkeypatch.setenv("MAIL_MEOW_BASE_URL", "https://mail-meow.example.com")
    monkeypatch.setenv("MAIL_MEOW_API_KEY", "api-key")
    monkeypatch.setenv("NOTIFICATION_EMAIL", "destination@example.com")
    config_path = tmp_path / "jqanywhere.toml"
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def initialize(context):\n    pass\n", encoding="utf-8")
    config_path.write_text(
        f'''
[strategy]
path = "{strategy_path}"

[notifications]
provider = "mailmeow"
''',
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.notifications.provider == "mailmeow"
    assert config.notifications.mail_meow_base_url == "https://mail-meow.example.com"


def test_config_rejects_incomplete_mailmeow_notifier(tmp_path, monkeypatch):
    monkeypatch.delenv("MAIL_MEOW_BASE_URL", raising=False)
    monkeypatch.delenv("MAIL_MEOW_API_KEY", raising=False)
    monkeypatch.delenv("NOTIFICATION_EMAIL", raising=False)
    config_path = tmp_path / "jqanywhere.toml"
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def initialize(context):\n    pass\n", encoding="utf-8")
    config_path.write_text(
        f'''
[strategy]
path = "{strategy_path}"

[notifications]
provider = "mailmeow"
''',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="MAIL_MEOW_BASE_URL"):
        load_config(config_path)


def test_factory_builds_mailmeow_notifier(tmp_path, monkeypatch):
    monkeypatch.setenv("MAIL_MEOW_BASE_URL", "https://mail-meow.example.com")
    monkeypatch.setenv("MAIL_MEOW_API_KEY", "api-key")
    monkeypatch.setenv("NOTIFICATION_EMAIL", "destination@example.com")
    config_path = tmp_path / "jqanywhere.toml"
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def initialize(context):\n    pass\n", encoding="utf-8")
    config_path.write_text(
        f'''
[strategy]
path = "{strategy_path}"

[notifications]
provider = "mailmeow"
''',
        encoding="utf-8",
    )

    engine = build_engine(load_config(config_path))

    assert isinstance(engine.notifier, MailMeowNotifier)


def test_mailmeow_posts_notification(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr("jqanywhere.notifications.mailmeow.urlopen", fake_urlopen)
    notifier = MailMeowNotifier("https://mail-meow.example.com/", "api/key", "destination@example.com", timeout_seconds=3.0)

    notifier.send("Subject", "Meow")

    request, timeout = requests[0]
    assert request.full_url == "https://mail-meow.example.com/api/api%2Fkey/email"
    assert request.method == "POST"
    assert timeout == 3.0
    assert request.get_header("Accept") == "*/*"
    assert request.get_header("Content-type") == "application/json"
    assert json.loads(request.data.decode("utf-8")) == {
        "to": "destination@example.com",
        "subject": "Subject",
        "text": "Meow",
    }


def test_mailmeow_requires_configuration(monkeypatch):
    monkeypatch.delenv("MAIL_MEOW_BASE_URL", raising=False)
    monkeypatch.delenv("MAIL_MEOW_API_KEY", raising=False)
    monkeypatch.delenv("NOTIFICATION_EMAIL", raising=False)

    with pytest.raises(ValueError, match="MAIL_MEOW_BASE_URL, MAIL_MEOW_API_KEY, NOTIFICATION_EMAIL"):
        MailMeowNotifier()
