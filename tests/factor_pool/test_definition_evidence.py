import pandas as pd

from factor_pool.audit.definition_evidence import build_definition_evidence


def test_definition_evidence_matches_exact_financial_grouped_technical_and_alpha():
    candidates = pd.DataFrame([
        {"vendor_field_name": "debt_ratio", "vendor_category": "financial_indicator"},
        {"vendor_field_name": "MA5", "vendor_category": "moving_average_indicator"},
        {"vendor_field_name": "WorldQuant_alpha001", "vendor_category": "alpha101"},
    ])
    tables = [
        pd.DataFrame([["debt_ratio", "ratio", "liabilities/assets", "l/a"]]),
        pd.DataFrame([["MA3, 5, 10", "MA N=3,5,10", "MA(CLOSE,N)"]]),
    ]

    result = build_definition_evidence(candidates, tables=tables, source_url="https://official.test").set_index("factor_id")

    assert result["definition_verified"].all()
    assert result.loc["debt_ratio", "definition"] == "l/a"
    assert result.loc["MA5", "definition"] == "MA(CLOSE,N)"
    assert "alpha #001" in result.loc["WorldQuant_alpha001", "definition"]
