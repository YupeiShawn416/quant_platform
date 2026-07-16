from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping


def normalize_records(records: Iterable[Mapping[str, object]]) -> list[dict[str, str]]:
    unique: dict[str, str] = {}
    for record in records:
        raw_name = record.get("vendor_field_name")
        raw_category = record.get("vendor_category")
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise ValueError("vendor_field_name must be a non-empty string")
        if not isinstance(raw_category, str) or not raw_category.strip():
            raise ValueError("vendor_category must be a non-empty string")
        name = raw_name.strip()
        category = raw_category.strip()
        previous = unique.get(name)
        if previous is not None and previous != category:
            raise ValueError(f"field appears in multiple vendor categories: {name}")
        unique[name] = category
    return [
        {"vendor_field_name": name, "vendor_category": unique[name]}
        for name in sorted(unique)
    ]


def catalog_sha256(records: Iterable[Mapping[str, object]]) -> str:
    names = [str(record["vendor_field_name"]) for record in records]
    payload = "\n".join(names).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
