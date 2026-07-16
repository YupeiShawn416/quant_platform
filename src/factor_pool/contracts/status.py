from enum import StrEnum


class IngredientStatus(StrEnum):
    PREFERRED = "preferred"
    SPECIALIZED = "specialized"
    SPARSE = "sparse"
    INSUFFICIENT_HISTORY = "insufficient_history"
    PENDING_REVIEW = "pending_review"
    NOT_APPLICABLE = "not_applicable"


class PitStatus(StrEnum):
    PENDING = "pending"
    DOCUMENTATION_PASSED = "documentation_passed"
    SAMPLE_ALIGNMENT_PASSED = "sample_alignment_passed"
    VERIFIED = "verified"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


class FactorLifecycle(StrEnum):
    CANDIDATE_FACTOR = "candidate_factor"
    DEFINITION_VERIFIED = "definition_verified"
    SAMPLE_ALIGNMENT_PASSED = "sample_alignment_passed"
    PIT_VERIFIED = "pit_verified"
    ELIGIBLE = "eligible"
    MATERIALIZED = "materialized"
    QUARANTINED = "quarantined"
