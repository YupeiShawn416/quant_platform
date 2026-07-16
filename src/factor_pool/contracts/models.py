from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from factor_pool.contracts.status import FactorLifecycle, PitStatus


@dataclass(frozen=True)
class AuditTransition:
    old_state: FactorLifecycle
    new_state: FactorLifecycle
    reason: str
    rule_version: str
    changed_at: datetime


@dataclass(frozen=True)
class ControlFieldDefinition:
    control_id: str
    control_version: str
    field_role: str
    provider: str
    source_dataset: str
    source_field: str
    availability_rule: str
    definition_status: str = "pending"
    pit_status: PitStatus = PitStatus.PENDING
    applicable_universe: str = "cn_equity"
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.field_role not in {"exposure_field", "filter_field"}:
            raise ValueError("control field_role must be exposure_field or filter_field")
        for name in (
            "control_id", "control_version", "provider", "source_dataset", "source_field", "availability_rule"
        ):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must not be blank")


_ALLOWED_TRANSITIONS = {
    FactorLifecycle.CANDIDATE_FACTOR: {
        FactorLifecycle.DEFINITION_VERIFIED,
        FactorLifecycle.QUARANTINED,
    },
    FactorLifecycle.DEFINITION_VERIFIED: {
        FactorLifecycle.SAMPLE_ALIGNMENT_PASSED,
        FactorLifecycle.QUARANTINED,
    },
    FactorLifecycle.SAMPLE_ALIGNMENT_PASSED: {
        FactorLifecycle.PIT_VERIFIED,
        FactorLifecycle.QUARANTINED,
    },
    FactorLifecycle.PIT_VERIFIED: {FactorLifecycle.ELIGIBLE},
    FactorLifecycle.ELIGIBLE: {FactorLifecycle.MATERIALIZED},
    FactorLifecycle.MATERIALIZED: set(),
    FactorLifecycle.QUARANTINED: set(),
}


def transition_factor(
    current: FactorLifecycle,
    target: FactorLifecycle,
    *,
    reason: str,
    rule_version: str,
    changed_at: datetime | None = None,
) -> AuditTransition:
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"illegal factor lifecycle transition: {current.value} -> {target.value}")
    if not reason.strip() or not rule_version.strip():
        raise ValueError("transition reason and rule_version are required")
    timestamp = changed_at or datetime.now().astimezone()
    if timestamp.tzinfo is None:
        raise ValueError("changed_at must be timezone-aware")
    return AuditTransition(current, target, reason, rule_version, timestamp)
