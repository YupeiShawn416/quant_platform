from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from rq_platform.settings import settings


AUDIT_DATES = ["2026-07-09", "2026-07-10", "2026-07-13"]
FIELD_CANDIDATES = [
    "market_cap",
    "total_market_cap",
    "circulating_market_cap",
    "float_market_cap",
    "a_share_market_val",
    "market_value",
    "turnover_rate",
    "turnover_ratio",
    "turnover",
    "volume_turnover",
]


def main() -> int:
    report = audit_valuation_fields()
    output_dir = Path("reports/generated")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "valuation_factor_field_audit.json"
    md_path = output_dir / "valuation_factor_field_audit.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    print(f"json={json_path}")
    print(f"markdown={md_path}")
    for date, row in report["dates"].items():
        print(f"{date}: rows={row['row_count']}")
        for field in FIELD_CANDIDATES:
            stats = row["fields"][field]
            if stats["exists"]:
                print(f"  {field}: non_null={stats['non_null_count']} ratio={stats['non_null_ratio']:.6f}")
            else:
                print(f"  {field}: missing")
    return 0


def audit_valuation_fields() -> dict:
    path = settings.data_root_path / "valuation_1d" / "year=2026.parquet"
    if not path.exists():
        raise FileNotFoundError(f"valuation parquet not found: {path}")
    frame = pd.read_parquet(path)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
    dates: dict[str, dict] = {}
    for trade_date in AUDIT_DATES:
        part = frame[frame["trade_date"] == trade_date]
        fields = {field: _field_stats(part, field) for field in FIELD_CANDIDATES}
        dates[trade_date] = {
            "row_count": int(len(part)),
            "columns": list(frame.columns),
            "fields": fields,
        }
    return {
        "dataset": "valuation_1d",
        "path": str(path),
        "audit_dates": AUDIT_DATES,
        "factor_field_mapping": {
            "market_cap": ["market_cap", "total_market_cap", "circulating_market_cap"],
            "turnover_rate": ["turnover_rate", "turnover_ratio"],
        },
        "dates": dates,
    }


def _field_stats(frame: pd.DataFrame, field: str) -> dict:
    if field not in frame.columns:
        return {
            "exists": False,
            "non_null_count": 0,
            "non_null_ratio": 0.0,
            "min": None,
            "max": None,
            "sample_values": [],
        }
    values = pd.to_numeric(frame[field], errors="coerce")
    non_null = values.dropna()
    return {
        "exists": True,
        "non_null_count": int(non_null.size),
        "non_null_ratio": float(non_null.size / len(frame)) if len(frame) else 0.0,
        "min": float(non_null.min()) if not non_null.empty else None,
        "max": float(non_null.max()) if not non_null.empty else None,
        "sample_values": [float(value) for value in non_null.head(5).tolist()],
    }


def _markdown(report: dict) -> str:
    lines = [
        "# Valuation Factor Field Audit",
        "",
        f"- dataset: `{report['dataset']}`",
        f"- path: `{report['path']}`",
        "",
        "| date | field | exists | non_null | ratio | min | max |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for trade_date, row in report["dates"].items():
        for field in FIELD_CANDIDATES:
            stats = row["fields"][field]
            lines.append(
                "| {date} | {field} | {exists} | {count} | {ratio:.6f} | {min} | {max} |".format(
                    date=trade_date,
                    field=field,
                    exists=str(stats["exists"]).lower(),
                    count=stats["non_null_count"],
                    ratio=stats["non_null_ratio"],
                    min=stats["min"],
                    max=stats["max"],
                )
            )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
