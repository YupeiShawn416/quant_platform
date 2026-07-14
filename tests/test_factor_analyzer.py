from rq_platform.factors.factor_analyzer import FactorAnalyzer
from rq_platform.factors.factor_calculator import FactorCalculator
from rq_platform.factors.factor_store import FactorStore

from factor_test_utils import write_factor_test_lake


def test_factor_analyzer_writes_summary_files(tmp_path):
    data_root = tmp_path / "data"
    factor_root = tmp_path / "factor_library"
    write_factor_test_lake(data_root)
    store = FactorStore(factor_root)
    FactorCalculator(data_root=data_root, store=store).compute(["market_cap"], "2026-05-01", "2026-07-10")

    FactorAnalyzer(data_root=data_root, store=store).analyze("market_cap")

    assert (factor_root / "analysis" / "market_cap" / "factor_summary.json").exists()
    assert (factor_root / "analysis" / "market_cap" / "factor_summary.md").exists()

