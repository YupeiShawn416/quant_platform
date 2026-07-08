import pytest

from rq_platform.backtest.strategy_loader import StrategyLoadError, load_strategy_module


def test_load_strategy_module_with_generate_weights(tmp_path):
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text(
        "def generate_weights(context, data):\n"
        "    return {'000001.XSHE': 1.0}\n",
        encoding="utf-8",
    )

    module = load_strategy_module(strategy_path)

    assert module.generate_weights(None, None) == {"000001.XSHE": 1.0}


def test_load_strategy_module_requires_generate_weights(tmp_path):
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("VALUE = 1\n", encoding="utf-8")

    with pytest.raises(StrategyLoadError, match="generate_weights"):
        load_strategy_module(strategy_path)
