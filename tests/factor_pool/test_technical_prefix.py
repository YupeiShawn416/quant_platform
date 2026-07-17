import pandas as pd

from factor_pool.audit.technical_prefix import compare_factor_prefixes


def test_compare_factor_prefixes_reports_each_factor_and_nan_safe_equality():
    index = pd.MultiIndex.from_tuples(
        [("A.X", pd.Timestamp("2025-01-02")), ("B.X", pd.Timestamp("2025-01-02"))],
        names=["order_book_id", "date"],
    )
    prefix = pd.DataFrame({"stable": [1.0, None], "changed": [2.0, 3.0]}, index=index)
    extended = pd.DataFrame({"stable": [1.0, None], "changed": [2.1, 3.0]}, index=index)

    result = compare_factor_prefixes(prefix, extended).set_index("factor_id")

    assert bool(result.loc["stable", "prefix_stable"]) is True
    assert bool(result.loc["changed", "prefix_stable"]) is False
    assert result.loc["changed", "mismatch_count"] == 1
    assert result.loc["stable", "comparison_count"] == 2
