from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_SYMBOLS = [
    "600519.XSHG",
    "000001.XSHE",
    "300750.XSHE",
    "688001.XSHG",
    "000005.XSHE",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Small-sample RQData probe for China HXZ fields.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--start-date", default="2025-01-02")
    parser.add_argument("--end-date", default="2025-01-10")
    parser.add_argument("--output-dir", default="reports/data_audit")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / "rqdata_hxz_probe.md"
    json_path = output_dir / "rqdata_hxz_probe.json"

    token = os.getenv("RQDATAC_KEY")
    if not token:
        report = {
            "status": "blocked",
            "reason": "RQDATAC_KEY is not set in this shell. No RQData call was made.",
            "symbols": args.symbols.split(","),
            "start_date": args.start_date,
            "end_date": args.end_date,
        }
        _write_outputs(report, md_path, json_path)
        print(f"status={report['status']}")
        print(f"reason={report['reason']}")
        print(f"markdown={md_path}")
        print(f"json={json_path}")
        return 2

    report = _run_probe(
        token=token,
        symbols=[item.strip() for item in args.symbols.split(",") if item.strip()],
        start_date=args.start_date,
        end_date=args.end_date,
    )
    _write_outputs(report, md_path, json_path)
    print(f"status={report['status']}")
    print(f"markdown={md_path}")
    print(f"json={json_path}")
    return 0 if report["status"] == "success" else 1


def _run_probe(token: str, symbols: list[str], start_date: str, end_date: str) -> dict[str, Any]:
    try:
        import rqdatac  # type: ignore
    except Exception as exc:
        return {
            "status": "failed",
            "error": f"rqdatac import failed: {type(exc).__name__}: {exc}",
            "symbols": symbols,
            "start_date": start_date,
            "end_date": end_date,
        }

    report: dict[str, Any] = {
        "status": "success",
        "symbols": symbols,
        "start_date": start_date,
        "end_date": end_date,
        "api_capabilities": {},
        "samples": {},
        "errors": [],
    }
    try:
        rqdatac.init(username="license", password=token)
    except Exception as exc:
        report["status"] = "failed"
        report["errors"].append({"step": "init", "error": f"{type(exc).__name__}: {exc}"})
        return report

    names = set(dir(rqdatac))
    for name in [
        "get_price",
        "get_factor",
        "get_all_factor_names",
        "get_financials",
        "query",
        "fundamentals",
        "get_turnover_rate",
        "all_instruments",
    ]:
        report["api_capabilities"][name] = name in names

    _probe_call(report, "price_none", lambda: rqdatac.get_price(
        symbols,
        start_date=start_date,
        end_date=end_date,
        frequency="1d",
        fields=["close", "volume", "total_turnover"],
        adjust_type="none",
        expect_df=True,
    ))
    if report["api_capabilities"].get("get_factor"):
        _probe_call(report, "valuation_factor", lambda: rqdatac.get_factor(
            symbols,
            ["market_cap", "market_cap_2", "pb_ratio", "pe_ratio"],
            start_date=start_date,
            end_date=end_date,
            expect_df=True,
        ))
    if report["api_capabilities"].get("get_turnover_rate"):
        _probe_call(report, "turnover_rate", lambda: rqdatac.get_turnover_rate(
            symbols,
            start_date=start_date,
            end_date=end_date,
        ))
    if report["api_capabilities"].get("get_all_factor_names"):
        _probe_call(report, "factor_names_sample", lambda: pd.DataFrame({
            "factor_name": list(rqdatac.get_all_factor_names(market="cn"))[:200]
        }))
    return report


def _probe_call(report: dict[str, Any], name: str, func) -> None:
    try:
        result = func()
        frame = result if isinstance(result, pd.DataFrame) else pd.DataFrame(result)
        report["samples"][name] = {
            "status": "success",
            "rows": int(len(frame)),
            "columns": list(frame.columns),
            "dtypes": {col: str(dtype) for col, dtype in frame.dtypes.items()},
            "head": frame.head(3).astype(str).to_dict("records"),
        }
    except Exception as exc:
        report["samples"][name] = {
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
        }


def _write_outputs(report: dict[str, Any], md_path: Path, json_path: Path) -> None:
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# RQData HXZ Probe", "", f"Status: `{report['status']}`", ""]
    if report["status"] == "blocked":
        lines.append(report["reason"])
    if report.get("errors"):
        lines.extend(["## Errors", ""])
        for item in report["errors"]:
            lines.append(f"- {item['step']}: {item['error']}")
    if report.get("api_capabilities"):
        lines.extend(["## API Capabilities", ""])
        for name, available in report["api_capabilities"].items():
            lines.append(f"- `{name}`: {available}")
    if report.get("samples"):
        lines.extend(["", "## Samples", ""])
        for name, sample in report["samples"].items():
            lines.append(f"### {name}")
            lines.append("")
            lines.append(f"- status: {sample['status']}")
            if sample["status"] == "success":
                lines.append(f"- rows: {sample['rows']}")
                lines.append(f"- columns: {', '.join(sample['columns'])}")
            else:
                lines.append(f"- error: {sample['error']}")
            lines.append("")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
