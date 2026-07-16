import math

import pandas as pd
import pytest

from factor_pool.engine.recipes import build_vendor_passthrough, evaluate_recipe, validate_recipe


def test_identity_recipe_preserves_values_nan_and_natural_direction():
    recipe = validate_recipe(
        {
            "factor_id": "rq_pe_ratio_ttm",
            "version": "1.0.0",
            "factor_kind": "vendor_pass_through",
            "inputs": [{"provider": "rqdata", "field": "pe_ratio_ttm"}],
            "formula": {"function": "identity", "arguments": ["pe_ratio_ttm"]},
            "value_direction": "natural",
            "eligible_for_model": False,
        },
        catalog={"pe_ratio_ttm": {"definition_status": "definition_verified", "pit_status": "sample_alignment_passed"}},
    )
    result = evaluate_recipe(recipe, {"pe_ratio_ttm": pd.Series([3.0, math.nan, -1.0])})

    assert result.iloc[0] == 3.0
    assert math.isnan(result.iloc[1])
    assert result.iloc[2] == -1.0
    assert recipe.eligible_for_model is False


def test_identity_recipe_rejects_dynamic_code_multiple_inputs_and_unreviewed_candidates():
    base = {
        "factor_id": "bad",
        "version": "1.0.0",
        "factor_kind": "vendor_pass_through",
        "inputs": [{"provider": "rqdata", "field": "x"}],
        "formula": {"function": "eval", "arguments": ["__import__('os')"]},
        "eligible_for_model": False,
    }
    with pytest.raises(ValueError, match="recipe function is not allowed"):
        validate_recipe(base, catalog={"x": {"definition_status": "definition_verified", "pit_status": "verified"}})

    multiple = {**base, "formula": {"function": "identity", "arguments": ["x", "y"]}}
    with pytest.raises(ValueError, match="identity requires exactly one input"):
        validate_recipe(multiple, catalog={"x": {"definition_status": "definition_verified", "pit_status": "verified"}})

    pending = {**base, "formula": {"function": "identity", "arguments": ["x"]}}
    with pytest.raises(ValueError, match="candidate has not passed definition and PIT gates"):
        validate_recipe(pending, catalog={"x": {"definition_status": "pending", "pit_status": "pending"}})


def test_build_vendor_passthrough_never_marks_candidate_eligible():
    recipe = build_vendor_passthrough({
        "factor_id": "pe_ratio_ttm",
        "vendor_category": "eod_indicator",
        "definition_status": "definition_verified",
        "pit_status": "sample_alignment_passed",
        "eligible_for_model": True,
    })

    assert recipe.factor_id == "rq_pe_ratio_ttm"
    assert recipe.factor_kind == "vendor_pass_through"
    assert recipe.function == "identity"
    assert recipe.eligible_for_model is False
