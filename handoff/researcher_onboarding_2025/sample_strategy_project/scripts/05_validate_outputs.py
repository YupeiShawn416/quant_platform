from __future__ import annotations

import sys

import pandas as pd

from common import load_config, project_path


def validate_weights(weights: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    required = {"trade_date", "order_book_id", "target_weight"}
    missing = required - set(weights.columns)
    if missing:
        errors.append(f"missing columns: {sorted(missing)}")
        return errors

    if weights.empty:
        errors.append("weights is empty")
        return errors

    if weights["order_book_id"].isna().any():
        errors.append("order_book_id contains empty values")

    weights["trade_date"] = pd.to_datetime(weights["trade_date"], errors="coerce")
    if weights["trade_date"].isna().any():
        errors.append("trade_date contains invalid dates")

    weights["target_weight"] = pd.to_numeric(weights["target_weight"], errors="coerce")
    if weights["target_weight"].isna().any():
        errors.append("target_weight contains non-numeric values")
    if (weights["target_weight"] < 0).any():
        errors.append("target_weight contains negative values")

    duplicates = weights.duplicated(["trade_date", "order_book_id"]).sum()
    if duplicates:
        errors.append(f"duplicate trade_date/order_book_id rows: {duplicates}")

    daily_sum = weights.groupby("trade_date")["target_weight"].sum()
    if (daily_sum > 1.000001).any():
        errors.append("daily target_weight sum exceeds 1.0")

    return errors


def main() -> int:
    config = load_config()
    weights_path = project_path(config["output"]["weights_path"])
    report_path = project_path("reports/validation_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)

    if not weights_path.exists():
        print("找不到 weights 文件，请先运行 scripts/04_generate_weights.py。")
        return 1

    weights = pd.read_csv(weights_path)
    errors = validate_weights(weights)

    if errors:
        body = "# Validation Report\n\nStatus: failed\n\n" + "\n".join(
            f"- {error}" for error in errors
        )
        report_path.write_text(body + "\n", encoding="utf-8")
        print(f"validation failed: {report_path}")
        for error in errors:
            print(f"- {error}")
        return 1

    daily_count = weights["trade_date"].nunique()
    body = (
        "# Validation Report\n\n"
        "Status: passed\n\n"
        f"- rows: {len(weights)}\n"
        f"- trading days: {daily_count}\n"
        f"- names: {weights['order_book_id'].nunique()}\n"
    )
    report_path.write_text(body, encoding="utf-8")
    print(f"validation passed: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
