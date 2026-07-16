import pandas as pd

from factor_pool.audit.ingredient_health import IngredientHealthConfig, evaluate_ingredient_health


def test_ingredient_health_assigns_preferred_and_specialized_without_misclassifying_industry_fields():
    observations = _observations()
    result = evaluate_ingredient_health(observations, _config())
    rows = result.set_index("vendor_field_name")

    assert rows.loc["broad", "ingredient_status"] == "preferred"
    assert rows.loc["bank_only", "ingredient_status"] == "specialized"
    assert rows.loc["bank_only", "applicable_universe"] == "citics_2019_l1:bank"
    assert rows.loc["bank_only", "coverage_rate"] == 0.5
    assert rows.loc["bank_only", "industry_concentration"] == 1.0


def test_ingredient_health_assigns_sparse_insufficient_history_and_pending_review():
    result = evaluate_ingredient_health(_observations(), _config()).set_index("vendor_field_name")

    assert result.loc["sparse", "ingredient_status"] == "sparse"
    assert result.loc["short", "ingredient_status"] == "insufficient_history"
    assert result.loc["middle", "ingredient_status"] == "pending_review"
    assert result.loc["broad", "usable_year_count"] == 2
    assert result["quality_snapshot_id"].str.len().eq(64).all()


def _config():
    return IngredientHealthConfig(
        rule_version="test-1",
        preferred_coverage=0.8,
        specialized_coverage=0.8,
        sparse_coverage=0.2,
        annual_coverage=0.5,
        preferred_years=2,
        specialized_years=2,
        minimum_history_years=2,
        minimum_quarters_per_year=3,
        industry_system="citics_2019",
        industry_level=1,
    )


def _observations():
    rows = []
    dates = pd.to_datetime([
        "2024-03-29", "2024-06-28", "2024-09-30", "2024-12-31",
        "2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31",
    ])
    for date_index, signal_date in enumerate(dates):
        for order_book_id, industry in [("BANK.X", "bank"), ("TECH.X", "tech")]:
            values = {
                "broad": 1.0,
                "bank_only": 1.0 if industry == "bank" else None,
                "sparse": 1.0 if date_index == 0 and industry == "bank" else None,
                "short": 1.0 if signal_date.year == 2025 else None,
                "middle": 1.0 if date_index % 4 != 3 else None,
            }
            for field, value in values.items():
                rows.append({
                    "signal_date": signal_date,
                    "order_book_id": order_book_id,
                    "vendor_field_name": field,
                    "value": value,
                    "industry_code": industry,
                    "universe_member": True,
                })
    return pd.DataFrame(rows)
