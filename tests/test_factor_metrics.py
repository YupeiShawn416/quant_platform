from rq_platform.factors.factor_analyzer import FactorAnalyzer
from rq_platform.factors.factor_calculator import FactorCalculator
from rq_platform.factors.factor_store import FactorStore

from factor_test_utils import write_factor_test_lake


def test_factor_analyzer_generates_ic_groups_turnover_top_bottom(tmp_path):
    data_root = tmp_path / "data"
    write_factor_test_lake(data_root)
    store = FactorStore(tmp_path / "factor_library")
    FactorCalculator(data_root=data_root, store=store).compute(["momentum_20d"], "2026-05-01", "2026-07-10")

    summary = FactorAnalyzer(data_root=data_root, store=store).analyze("momentum_20d")

    assert summary["factor_id"] == "momentum_20d"
    assert store.read_analysis_csv("momentum_20d", "ic_daily.csv").shape[0] > 0
    assert store.read_analysis_csv("momentum_20d", "group_returns.csv").shape[0] > 0
    assert store.read_analysis_csv("momentum_20d", "turnover.csv").shape[0] > 0
    assert store.read_analysis_csv("momentum_20d", "top_bottom_latest.csv").shape[0] > 0

