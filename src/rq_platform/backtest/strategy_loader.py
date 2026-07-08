from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


class StrategyLoadError(ValueError):
    pass


def load_strategy_module(strategy_path: str | Path) -> ModuleType:
    path = Path(strategy_path).expanduser().resolve()
    if not path.exists():
        raise StrategyLoadError(f"strategy file not found: {path}")
    if not path.is_file():
        raise StrategyLoadError(f"strategy path is not a file: {path}")

    module_name = f"rq_platform_user_strategy_{path.stem}_{abs(hash(path))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise StrategyLoadError(f"cannot load strategy module: {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    generate_weights = getattr(module, "generate_weights", None)
    if not callable(generate_weights):
        raise StrategyLoadError(
            f"strategy must define callable generate_weights(context, data): {path}"
        )
    return module
