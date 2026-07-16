from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import pandas as pd


FINANCIAL_CATEGORIES = {
    "eod_indicator",
    "operational_indicator",
    "cash_flow_indicator",
    "financial_indicator",
    "growth_indicator",
}
TECHNICAL_CATEGORIES = {
    "alpha101",
    "moving_average_indicator",
    "obos_indicator",
    "energy_indicator",
}


@dataclass(frozen=True)
class VendorAuditConfig:
    rule_version: str

    def __post_init__(self) -> None:
        if not self.rule_version.strip():
            raise ValueError("vendor audit rule_version is required")


def audit_vendor_candidates(
    candidates: pd.DataFrame,
    *,
    definitions: Mapping[str, str],
    event_observations: pd.DataFrame,
    technical_observations: pd.DataFrame,
    config: VendorAuditConfig,
) -> pd.DataFrame:
    required = {"vendor_field_name", "vendor_category", "classification_status"}
    missing = required - set(candidates.columns)
    if missing:
        raise ValueError(f"vendor candidates missing columns: {', '.join(sorted(missing))}")
    invalid = candidates.loc[candidates["classification_status"] != "candidate_factor"]
    if not invalid.empty:
        raise ValueError("vendor audit accepts candidate_factor rows only")
    if candidates["vendor_field_name"].duplicated().any():
        raise ValueError("vendor candidate factor IDs must be unique")

    rows = []
    for candidate in candidates.sort_values("vendor_field_name").itertuples(index=False):
        factor_id = str(candidate.vendor_field_name)
        category = str(candidate.vendor_category)
        definition = str(definitions.get(factor_id, "")).strip()
        if not definition:
            pit_status, evidence_count, failure_reason = "pending", 0, "definition metadata missing"
            definition_status = "pending"
            audit_type = _audit_type(category)
        else:
            definition_status = "definition_verified"
            audit_type = _audit_type(category)
            if audit_type == "financial_event_window":
                pit_status, evidence_count, failure_reason = _audit_financial(factor_id, event_observations)
            elif audit_type == "technical_prefix_stability":
                pit_status, evidence_count, failure_reason = _audit_technical(factor_id, technical_observations)
            else:
                pit_status, evidence_count, failure_reason = "documentation_passed", 0, None
        rows.append({
            "factor_id": factor_id,
            "vendor_category": category,
            "definition_status": definition_status,
            "pit_status": pit_status,
            "audit_type": audit_type,
            "evidence_count": int(evidence_count),
            "failure_reason": failure_reason,
            "audit_rule_version": config.rule_version,
            "eligible_for_model": False,
        })
    result = pd.DataFrame(rows)
    if not result.empty:
        result["eligible_for_model"] = result["eligible_for_model"].astype(object)
    return result


def _audit_type(category: str) -> str:
    if category in FINANCIAL_CATEGORIES:
        return "financial_event_window"
    if category in TECHNICAL_CATEGORIES:
        return "technical_prefix_stability"
    return "documentation_only"


def _audit_financial(factor_id: str, observations: pd.DataFrame) -> tuple[str, int, str | None]:
    if observations.empty or "factor_id" not in observations:
        return "documentation_passed", 0, None
    part = observations.loc[observations["factor_id"].astype(str) == factor_id].copy()
    if part.empty:
        return "documentation_passed", 0, None
    required = {"announcement_date", "observation_date", "source_signature", "expected_source_signature"}
    missing = required - set(part.columns)
    if missing:
        raise ValueError(f"PIT event observations missing columns: {', '.join(sorted(missing))}")
    part["announcement_date"] = pd.to_datetime(part["announcement_date"], errors="raise")
    part["observation_date"] = pd.to_datetime(part["observation_date"], errors="raise")
    uses_new = part["source_signature"].astype(str) == part["expected_source_signature"].astype(str)
    early = uses_new & (part["observation_date"] < part["announcement_date"])
    if early.any():
        return "failed", int(len(part)), "new report signature observed before announcement"
    after = uses_new & (part["observation_date"] >= part["announcement_date"])
    if after.any():
        return "sample_alignment_passed", int(len(part)), None
    return "documentation_passed", int(len(part)), "event sample did not observe new report signature"


def _audit_technical(factor_id: str, observations: pd.DataFrame) -> tuple[str, int, str | None]:
    if observations.empty or "factor_id" not in observations:
        return "documentation_passed", 0, None
    part = observations.loc[observations["factor_id"].astype(str) == factor_id]
    if part.empty:
        return "documentation_passed", 0, None
    if "prefix_stable" not in part:
        raise ValueError("technical observations missing prefix_stable")
    if not part["prefix_stable"].fillna(False).astype(bool).all():
        return "failed", int(len(part)), "historical prefix changed when later data was appended"
    return "sample_alignment_passed", int(len(part)), None
