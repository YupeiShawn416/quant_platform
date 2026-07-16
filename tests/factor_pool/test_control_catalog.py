from datetime import datetime, timezone

import pytest

from factor_pool.catalog.control_catalog import (
    assert_controls_not_features,
    build_control_catalog,
    load_control_definitions,
)


def test_control_catalog_contains_required_infrastructure_controls():
    definitions = load_control_definitions()
    frame = build_control_catalog(
        definitions,
        snapshot_id="controls-test",
        created_at=datetime(2026, 7, 16, tzinfo=timezone.utc),
    )

    assert set(frame["control_id"]) == {
        "industry_citics_2019_l1",
        "log_float_market_cap",
        "is_st",
        "is_suspended",
        "is_limit_up",
        "is_limit_down",
        "is_listed",
        "listed_days",
    }
    assert set(frame["field_role"]) == {"exposure_field", "filter_field"}
    assert frame["eligible_for_model"].eq(False).all()
    assert frame["definition_status"].eq("definition_verified").all()


def test_control_catalog_rejects_duplicates_and_feature_leakage():
    definitions = load_control_definitions()
    with pytest.raises(ValueError, match="duplicate control_id"):
        build_control_catalog(
            [definitions[0], definitions[0]],
            snapshot_id="duplicate",
            created_at=datetime.now(timezone.utc),
        )

    with pytest.raises(ValueError, match="control fields leaked into model features: is_st, log_float_market_cap"):
        assert_controls_not_features(
            {"is_st", "log_float_market_cap", "is_suspended"},
            {"momentum_20d", "is_st", "log_float_market_cap"},
        )
