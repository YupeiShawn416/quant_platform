from rq_platform.factors.factor_registry import FactorRegistry


def test_factor_registry_lists_five_builtin_factors():
    rows = FactorRegistry().list_factors()
    assert len(rows) == 5
    assert {row["factor_id"] for row in rows} == {
        "market_cap",
        "turnover_rate",
        "momentum_20d",
        "reversal_5d",
        "volatility_20d",
    }

