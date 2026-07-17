from __future__ import annotations

import re
from collections.abc import Sequence

import pandas as pd


FINANCIAL_CATEGORIES = {
    "eod_indicator", "operational_indicator", "cash_flow_indicator",
    "financial_indicator", "growth_indicator",
}
TECHNICAL_CATEGORIES = {
    "moving_average_indicator", "obos_indicator", "energy_indicator",
}


def build_definition_evidence(
    candidates: pd.DataFrame,
    *,
    tables: Sequence[pd.DataFrame],
    source_url: str,
) -> pd.DataFrame:
    rows = []
    for candidate in candidates.sort_values("vendor_field_name").itertuples(index=False):
        factor_id = str(candidate.vendor_field_name)
        category = str(candidate.vendor_category)
        match = _match_table(factor_id, category, tables)
        if category == "alpha101" and re.fullmatch(r"WorldQuant_alpha\d{3}", factor_id):
            number = factor_id.rsplit("alpha", 1)[1]
            match = (f"WorldQuant 101 Formulaic Alphas, alpha #{number}", factor_id)
        definition, source_locator = match if match else (None, None)
        rows.append({
            "factor_id": factor_id,
            "vendor_category": category,
            "definition": definition,
            "definition_source_url": source_url,
            "definition_source_locator": source_locator,
            "definition_verified": definition is not None,
        })
    return pd.DataFrame(rows)


def _match_table(factor_id: str, category: str, tables: Sequence[pd.DataFrame]):
    if category in FINANCIAL_CATEGORIES:
        for table in tables:
            if table.shape[1] < 4:
                continue
            matched = table.loc[table.iloc[:, 0].astype(str) == factor_id]
            if not matched.empty:
                row = matched.iloc[0]
                return str(row.iloc[3]), factor_id
    if category in TECHNICAL_CATEGORIES:
        for table in tables:
            if table.shape[1] != 3:
                continue
            field_family = str(table.iloc[:, 0].astype(str).iloc[0]) if len(table) == 1 else None
            for _, row in table.iterrows():
                field_family = str(row.iloc[0])
                if _technical_family_contains(field_family, factor_id):
                    return str(row.iloc[2]), field_family
    return None


def _technical_family_contains(field_family: str, factor_id: str) -> bool:
    normalized = field_family.replace("，", ",")
    if re.search(rf"(?<![A-Za-z0-9_]){re.escape(factor_id)}(?![A-Za-z0-9_])", normalized):
        return True
    candidate = re.fullmatch(r"([A-Z]+)(\d+)", factor_id)
    family = re.match(r"^([A-Z]+)(\d+)", normalized.strip())
    if not candidate or not family or candidate.group(1) != family.group(1):
        return False
    return int(candidate.group(2)) in {int(value) for value in re.findall(r"\d+", normalized)}
