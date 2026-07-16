from datetime import datetime

import pytest

from factor_pool.contracts.models import ControlFieldDefinition, transition_factor
from factor_pool.contracts.status import FactorLifecycle, IngredientStatus, PitStatus


def test_status_contracts_are_closed_and_stable():
    assert {item.value for item in IngredientStatus} == {
        "preferred", "specialized", "sparse", "insufficient_history", "pending_review", "not_applicable"
    }
    assert {item.value for item in PitStatus} == {
        "pending", "documentation_passed", "sample_alignment_passed", "verified", "failed", "not_applicable"
    }


def test_factor_lifecycle_records_legal_transition():
    event = transition_factor(
        FactorLifecycle.CANDIDATE_FACTOR,
        FactorLifecycle.DEFINITION_VERIFIED,
        reason="definition metadata exists",
        rule_version="1.1.0",
    )
    assert event.old_state == FactorLifecycle.CANDIDATE_FACTOR
    assert event.new_state == FactorLifecycle.DEFINITION_VERIFIED
    assert event.reason == "definition metadata exists"
    assert event.rule_version == "1.1.0"
    assert isinstance(event.changed_at, datetime)
    assert event.changed_at.tzinfo is not None


def test_factor_lifecycle_rejects_direct_eligibility():
    with pytest.raises(ValueError, match="illegal factor lifecycle transition"):
        transition_factor(
            FactorLifecycle.CANDIDATE_FACTOR,
            FactorLifecycle.ELIGIBLE,
            reason="skip audit",
            rule_version="1.1.0",
        )


@pytest.mark.parametrize("role", ["vendor_factor", "statement_field", "market_data"])
def test_control_definition_rejects_non_control_roles(role):
    with pytest.raises(ValueError, match="control field_role"):
        ControlFieldDefinition(
            control_id="bad",
            control_version="1.0.0",
            field_role=role,
            provider="quant_platform",
            source_dataset="x",
            source_field="y",
            availability_rule="known_on_signal_date",
        )
