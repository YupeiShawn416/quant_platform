from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from rq_platform.etl.daily_update_plan import DEFAULT_DAILY_DATASETS
from rq_platform.etl.daily_update_paths import STATUS_PATH
from rq_platform.settings import settings


CORE_DAILY_DATASETS = {"prices", "index_prices", "tradability", "valuation", "industry", "index_members"}
STATUS_TO_PARQUET_DATASETS = {
    "calendar": ["trading_calendar"],
    "instruments": ["instruments"],
    "index_prices": ["index_prices_1d"],
    "prices": ["prices_1d_pre", "prices_1d_none"],
    "tradability": ["tradability_1d"],
    "valuation": ["valuation_1d"],
    "industry": ["industry_classification"],
    "index_members": ["index_components", "index_weights"],
}


def reconcile_daily_update_coverage(
    *,
    status_path: str | Path | None = None,
    data_root: str | Path | None = None,
    expected_end_date: str | None = None,
) -> dict[str, Any]:
    status_file = Path(status_path).resolve() if status_path is not None else STATUS_PATH
    root = Path(data_root).resolve() if data_root is not None else settings.data_root_path
    status = _read_status(status_file)
    latest = _latest_status_by_dataset(status)
    datasets: list[dict[str, Any]] = []
    mismatch_datasets: list[str] = []
    zero_row_suspect_rows: list[dict[str, Any]] = []

    for dataset in DEFAULT_DAILY_DATASETS:
        row = latest.get(dataset, {})
        row_count = _int_or_zero(row.get("row_count"))
        status_value = str(row.get("status") or "")
        target_end = expected_end_date or str(row.get("end_date") or "")
        actual_max = _status_dataset_actual_max(root, dataset)
        status_mismatch = (
            status_value == "success"
            and bool(target_end)
            and (actual_max is None or actual_max < target_end)
        )
        zero_success = status_value == "success" and dataset in CORE_DAILY_DATASETS and row_count == 0
        if status_mismatch:
            mismatch_datasets.append(dataset)
        if zero_success:
            zero_row_suspect_rows.append(_clean_status_row(row))
        datasets.append(
            {
                "dataset": dataset,
                "latest_status": status_value or None,
                "status_end_date": target_end or None,
                "status_row_count": row_count if row else None,
                "actual_max_date": actual_max,
                "status_mismatch": status_mismatch,
                "zero_row_success": zero_success,
                "needs_repair": status_mismatch or zero_success,
            }
        )

    recommend_rsync = not mismatch_datasets and not zero_row_suspect_rows
    return {
        "status_path": str(status_file),
        "datasets": datasets,
        "mismatch_datasets": sorted(set(mismatch_datasets)),
        "zero_row_suspect_rows": zero_row_suspect_rows,
        "recommend_rsync": recommend_rsync,
    }


def write_reconcile_report(
    report: dict[str, Any],
    output_dir: str | Path = "reports/generated",
) -> tuple[Path, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "daily_update_reconcile.json"
    md_path = output / "daily_update_reconcile.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_reconcile_markdown(report), encoding="utf-8")
    return md_path, json_path


def render_reconcile_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Daily Update Coverage Reconcile",
        "",
        f"status_path: {report.get('status_path') or ''}",
        f"recommend_rsync: {report.get('recommend_rsync')}",
        f"mismatch_datasets: {', '.join(report.get('mismatch_datasets') or []) or '-'}",
        f"zero_row_suspect_count: {len(report.get('zero_row_suspect_rows') or [])}",
        "",
        "| dataset | latest status | status end | status rows | actual max date | mismatch | zero-row success | needs repair |",
        "| --- | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for item in report.get("datasets", []):
        lines.append(
            f"| {item.get('dataset') or ''} | {item.get('latest_status') or ''} | "
            f"{item.get('status_end_date') or ''} | {item.get('status_row_count') or 0} | "
            f"{item.get('actual_max_date') or ''} | {item.get('status_mismatch')} | "
            f"{item.get('zero_row_success')} | {item.get('needs_repair')} |"
        )
    return "\n".join(lines) + "\n"


def _read_status(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _latest_status_by_dataset(frame: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if frame.empty or "dataset" not in frame.columns:
        return {}
    latest: dict[str, dict[str, Any]] = {}
    for _, row in frame.iterrows():
        latest[str(row.get("dataset"))] = row.to_dict()
    return latest


def _status_dataset_actual_max(root: Path, dataset: str) -> str | None:
    values: list[str] = []
    for parquet_dataset in STATUS_TO_PARQUET_DATASETS.get(dataset, []):
        value = _dataset_max_date(root / parquet_dataset)
        if value:
            values.append(value)
    return min(values) if values else None


def _dataset_max_date(path: Path) -> str | None:
    files: list[Path]
    if path.is_file():
        files = [path]
    else:
        files = sorted(path.glob("*.parquet"))
    values: list[str] = []
    for file_path in files:
        value = _file_max_date(file_path)
        if value:
            values.append(value)
    return max(values) if values else None


def _file_max_date(path: Path) -> str | None:
    if not path.exists():
        return None
    for column in ["trade_date", "listed_date"]:
        try:
            frame = pd.read_parquet(path, columns=[column])
        except Exception:
            continue
        if frame.empty:
            continue
        dates = pd.to_datetime(frame[column], errors="coerce").dropna()
        if not dates.empty:
            return dates.max().strftime("%Y-%m-%d")
    return None


def _int_or_zero(value: Any) -> int:
    try:
        if pd.isna(value):
            return 0
        return int(value)
    except Exception:
        return 0


def _clean_status_row(row: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in row.items():
        clean[key] = None if pd.isna(value) else value
    return clean
