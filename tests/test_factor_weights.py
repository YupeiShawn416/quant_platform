import pandas as pd

from rq_platform.factors.factor_calculator import FactorCalculator
from rq_platform.factors.factor_store import FactorStore
from rq_platform.factors.factor_weights import FactorWeightGenerator

from factor_test_utils import write_factor_test_lake


def test_factor_weights_are_long_only_and_sum_to_one(tmp_path):
    data_root = tmp_path / "data"
    write_factor_test_lake(data_root)
    store = FactorStore(tmp_path / "factor_library")
    FactorCalculator(data_root=data_root, store=store).compute(["market_cap"], "2026-05-01", "2026-07-10")

    result = FactorWeightGenerator(store=store, output_root=tmp_path / "weights").generate(
        "market_cap",
        top_quantile=0.5,
        max_names=3,
    )
    weights = pd.read_csv(result["target_weights"])

    assert not weights.empty
    assert (weights["target_weight"] >= 0).all()
    assert (weights.groupby("trade_date")["target_weight"].sum() <= 1.000001).all()
    assert {"target_weights.csv", "manifest.json", "README.md"}.issubset(
        {path.name for path in (tmp_path / "weights" / result["output_dir"].split("/")[-1]).iterdir()}
    )

