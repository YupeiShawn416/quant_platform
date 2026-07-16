from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import pandas as pd


ALLOWED_FUNCTIONS = {"identity"}
ALLOWED_PIT_GATES = {"sample_alignment_passed", "verified"}


@dataclass(frozen=True)
class RecipeDefinition:
    factor_id: str
    version: str
    factor_kind: str
    input_field: str
    input_provider: str
    function: str
    value_direction: str
    eligible_for_model: bool


def validate_recipe(
    payload: Mapping[str, object],
    *,
    catalog: Mapping[str, Mapping[str, object]],
) -> RecipeDefinition:
    formula = payload.get("formula")
    if not isinstance(formula, Mapping):
        raise ValueError("recipe formula must be structured")
    function = str(formula.get("function", ""))
    if function not in ALLOWED_FUNCTIONS:
        raise ValueError(f"recipe function is not allowed: {function}")
    arguments = formula.get("arguments")
    if not isinstance(arguments, list) or len(arguments) != 1:
        raise ValueError("identity requires exactly one input")
    inputs = payload.get("inputs")
    if not isinstance(inputs, list) or len(inputs) != 1 or not isinstance(inputs[0], Mapping):
        raise ValueError("vendor pass-through recipe requires exactly one structured input")
    input_field = str(inputs[0].get("field", ""))
    if not input_field or str(arguments[0]) != input_field:
        raise ValueError("identity argument must match its input field")
    audit = catalog.get(input_field)
    if (
        audit is None
        or str(audit.get("definition_status")) != "definition_verified"
        or str(audit.get("pit_status")) not in ALLOWED_PIT_GATES
    ):
        raise ValueError("candidate has not passed definition and PIT gates")
    if bool(payload.get("eligible_for_model", False)):
        raise ValueError("recipe creation cannot grant model eligibility")
    factor_kind = str(payload.get("factor_kind", ""))
    if factor_kind != "vendor_pass_through":
        raise ValueError("identity provider recipe must use vendor_pass_through")
    return RecipeDefinition(
        factor_id=_required(payload, "factor_id"),
        version=_required(payload, "version"),
        factor_kind=factor_kind,
        input_field=input_field,
        input_provider=str(inputs[0].get("provider", "")),
        function=function,
        value_direction=str(payload.get("value_direction", "natural")),
        eligible_for_model=False,
    )


def evaluate_recipe(
    recipe: RecipeDefinition,
    inputs: Mapping[str, pd.Series],
) -> pd.Series:
    if recipe.function != "identity":
        raise ValueError(f"unsupported recipe function: {recipe.function}")
    if recipe.input_field not in inputs:
        raise KeyError(f"recipe input missing: {recipe.input_field}")
    return inputs[recipe.input_field].copy()


def build_vendor_passthrough(candidate: Mapping[str, object]) -> RecipeDefinition:
    factor_id = _required(candidate, "factor_id")
    payload = {
        "factor_id": f"rq_{factor_id}",
        "version": "1.0.0",
        "factor_kind": "vendor_pass_through",
        "inputs": [{"provider": "rqdata", "field": factor_id}],
        "formula": {"function": "identity", "arguments": [factor_id]},
        "value_direction": "natural",
        "eligible_for_model": False,
    }
    return validate_recipe(payload, catalog={factor_id: candidate})


def _required(payload: Mapping[str, object], name: str) -> str:
    value = str(payload.get(name, "")).strip()
    if not value:
        raise ValueError(f"recipe {name} is required")
    return value
