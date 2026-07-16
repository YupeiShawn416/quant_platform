import pandas as pd

from factor_pool.audit.vendor_factor import VendorAuditConfig, audit_vendor_candidates


def test_financial_candidate_passes_only_sample_alignment_when_change_starts_on_announcement():
    result = audit_vendor_candidates(
        _candidates([("pe_ratio_ttm", "eod_indicator")]),
        definitions={"pe_ratio_ttm": "Price divided by announced TTM earnings"},
        event_observations=pd.DataFrame([
            _event("pe_ratio_ttm", "2025-04-25", "2025-04-24", "old", "new"),
            _event("pe_ratio_ttm", "2025-04-25", "2025-04-25", "new", "new"),
        ]),
        technical_observations=pd.DataFrame(),
        config=VendorAuditConfig(rule_version="pit-test"),
    ).iloc[0]

    assert result["definition_status"] == "definition_verified"
    assert result["pit_status"] == "sample_alignment_passed"
    assert result["eligible_for_model"] is False


def test_one_preannouncement_new_signature_fails_entire_candidate():
    result = audit_vendor_candidates(
        _candidates([("roe_ttm", "financial_indicator")]),
        definitions={"roe_ttm": "Return on equity from announced statements"},
        event_observations=pd.DataFrame([
            _event("roe_ttm", "2025-04-25", "2025-04-24", "new", "new"),
            _event("roe_ttm", "2025-04-25", "2025-04-25", "new", "new"),
        ]),
        technical_observations=pd.DataFrame(),
        config=VendorAuditConfig(rule_version="pit-test"),
    ).iloc[0]

    assert result["pit_status"] == "failed"
    assert result["failure_reason"] == "new report signature observed before announcement"


def test_missing_definition_stays_pending_and_technical_prefix_test_is_separate():
    candidates = _candidates([("unknown", "eod_indicator"), ("WorldQuant_alpha001", "alpha101")])
    result = audit_vendor_candidates(
        candidates,
        definitions={"WorldQuant_alpha001": "WorldQuant alpha 001"},
        event_observations=pd.DataFrame(),
        technical_observations=pd.DataFrame([
            {"factor_id": "WorldQuant_alpha001", "observation_date": "2025-01-02", "prefix_stable": True},
            {"factor_id": "WorldQuant_alpha001", "observation_date": "2025-01-03", "prefix_stable": True},
        ]),
        config=VendorAuditConfig(rule_version="pit-test"),
    ).set_index("factor_id")

    assert result.loc["unknown", "definition_status"] == "pending"
    assert result.loc["unknown", "pit_status"] == "pending"
    assert result.loc["WorldQuant_alpha001", "pit_status"] == "sample_alignment_passed"


def _candidates(items):
    return pd.DataFrame([
        {"vendor_field_name": name, "vendor_category": category, "classification_status": "candidate_factor"}
        for name, category in items
    ])


def _event(factor_id, announcement_date, observation_date, source_signature, expected_source_signature):
    return {
        "factor_id": factor_id,
        "order_book_id": "000001.XSHE",
        "report_period": "2024q4",
        "announcement_date": announcement_date,
        "observation_date": observation_date,
        "value": 1.0,
        "source_signature": source_signature,
        "expected_source_signature": expected_source_signature,
    }
