"""Strategy module loading."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_strategy(path: str | Path, module_name: str = "jqanywhere_user_strategy") -> ModuleType:
    strategy_path = Path(path).resolve()
    if not strategy_path.exists():
        raise FileNotFoundError(strategy_path)
    spec = importlib.util.spec_from_file_location(module_name, strategy_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load strategy from {strategy_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
