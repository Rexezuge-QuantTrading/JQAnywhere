import json

import pytest

from jqanywhere.cli import main
from jqanywhere.config import load_config
from jqanywhere.jqcompat.api import before_trading_start, finance, handle_data, macro


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
    for func in (handle_data, before_trading_start, finance.run_query, macro.run_query):
        with pytest.raises(NotImplementedError, match="v0.5"):
            func(None)
