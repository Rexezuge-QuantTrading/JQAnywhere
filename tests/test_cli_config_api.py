import json

import pytest

from jqanywhere.cli import main
from jqanywhere.config import load_config
from jqanywhere.jqcompat.api import before_trading_start, finance, get_ticks, handle_data, macro, marginsec_open, normalize_code


def test_config_rejects_unknown_provider(tmp_path):
    config_path = tmp_path / "jqanywhere.toml"
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def initialize(context):\n    pass\n", encoding="utf-8")
    config_path.write_text(
        f'[strategy]\npath = "{strategy_path}"\n\n[data]\nprovider = "missing"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="data.provider"):
        load_config(config_path)


def test_config_accepts_remote_miniqmt_live_provider(tmp_path):
    config_path = tmp_path / "jqanywhere.toml"
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def initialize(context):\n    pass\n", encoding="utf-8")
    config_path.write_text(
        f'''
[strategy]
path = "{strategy_path}"

[runtime]
mode = "live"

[data]
provider = "remote_miniqmt"
endpoint = "http://127.0.0.1:8000"

[broker]
provider = "remote_miniqmt"
endpoint = "http://127.0.0.1:8000"
account_id = "1000000365"
''',
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.runtime.mode == "live"
    assert config.data.provider == "remote_miniqmt"
    assert config.broker.account_id == "1000000365"


def test_cli_config_validate_json(tmp_path, capsys):
    config_path = tmp_path / "jqanywhere.toml"
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def initialize(context):\n    pass\n", encoding="utf-8")
    config_path.write_text(f'[strategy]\nid = "cli"\npath = "{strategy_path}"\n', encoding="utf-8")

    main(["config", "validate", "--config", str(config_path), "--json"])

    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "valid"
    assert result["strategy_id"] == "cli"


def test_cli_run_json_outputs_valid_json(tmp_path, capsys):
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text(
        "from jqdata import *\n\ndef initialize(context):\n    run_daily(trade, '09:50')\n\ndef trade(context):\n    g.ran = True\n",
        encoding="utf-8",
    )
    config_path = tmp_path / "jqanywhere.toml"
    config_path.write_text(f'[strategy]\nid = "cli_run"\npath = "{strategy_path}"\n', encoding="utf-8")

    main(["run", "--config", str(config_path), "--now", "2026-05-18T09:50:00+08:00", "--json"])

    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "completed"
    assert result["state"] == {"ran": True}


def test_documented_unsupported_surfaces_are_explicit():
    for func in (handle_data, before_trading_start, finance.run_query, macro.run_query, get_ticks, normalize_code, marginsec_open):
        with pytest.raises(NotImplementedError, match="v0.9.0"):
            func(None)


def test_cli_doctor_json_reports_configured_providers(tmp_path, capsys):
    config_path = tmp_path / "jqanywhere.toml"
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def initialize(context):\n    pass\n", encoding="utf-8")
    config_path.write_text(f'[strategy]\nid = "doctor"\npath = "{strategy_path}"\n', encoding="utf-8")

    main(["doctor", "--config", str(config_path), "--json"])

    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "ok"
    assert {check["name"] for check in result["checks"]} >= {"config", "strategy_path", "data_provider", "broker_provider"}


def test_cli_doctor_reports_remote_miniqmt_live_readiness(tmp_path, capsys, monkeypatch):
    config_path = tmp_path / "jqanywhere.toml"
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def initialize(context):\n    pass\n", encoding="utf-8")
    config_path.write_text(
        f'''
[strategy]
path = "{strategy_path}"

[runtime]
mode = "live"

[data]
provider = "remote_miniqmt"
endpoint = "http://127.0.0.1:8000"
token_env = "TEST_MINIQMT_TOKEN"

[broker]
provider = "remote_miniqmt"
endpoint = "http://127.0.0.1:8000"
account_id = "1000000365"
enable_trading = false
''',
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_MINIQMT_TOKEN", "secret")

    main(["doctor", "--config", str(config_path), "--json"])

    result = json.loads(capsys.readouterr().out)
    checks = {check["name"]: check for check in result["checks"]}
    assert result["status"] == "ok"
    assert checks["remote_miniqmt_data_endpoint"]["message"] == "http://127.0.0.1:8000"
    assert checks["remote_miniqmt_data_token"]["message"] == "TEST_MINIQMT_TOKEN set"
    assert checks["remote_miniqmt_trading"]["message"] == "disabled/read-only"
