from rq_platform.factors.factor_calculator import FactorCalculator
from rq_platform.factors.factor_store import FactorStore

from factor_test_utils import write_factor_test_lake
import pandas as pd


def test_factor_calculator_computes_builtin_factors_without_duplicates(tmp_path):
    data_root = tmp_path / "data"
    write_factor_test_lake(data_root)
    calculator = FactorCalculator(data_root=data_root, store=FactorStore(tmp_path / "factor_library"))

    for factor_id in ["market_cap", "momentum_20d", "reversal_5d", "volatility_20d"]:
        frame = calculator.compute_factor(factor_id, "2026-05-01", "2026-07-10")
        assert not frame.empty
        assert {"trade_date", "order_book_id", "factor_value", "factor_score"}.issubset(frame.columns)
        assert not frame.duplicated(["trade_date", "order_book_id"]).any()


def test_factor_calculator_supports_csi300_universe(tmp_path):
    data_root = tmp_path / "data"
    write_factor_test_lake(data_root)
    calculator = FactorCalculator(data_root=data_root, store=FactorStore(tmp_path / "factor_library"))

    frame = calculator.compute_factor("market_cap", "2026-05-01", "2026-07-10", universe="csi300")

    assert frame["order_book_id"].nunique() == 3


def test_factor_calculator_selects_covered_valuation_candidate(tmp_path):
    data_root = tmp_path / "data"
    write_factor_test_lake(data_root)
    path = data_root / "valuation_1d" / "year=2026.parquet"
    valuation = pd.read_parquet(path)
    valuation["total_market_cap"] = valuation["market_cap"] * 2
    valuation["market_cap"] = pd.NA
    valuation.to_parquet(path, index=False)
    calculator = FactorCalculator(data_root=data_root, store=FactorStore(tmp_path / "factor_library"))

    frame = calculator.compute_factor("market_cap", "2026-05-01", "2026-07-10")

    assert not frame["factor_score"].isna().all()
    assert set(frame["source_field"]) == {"total_market_cap"}
