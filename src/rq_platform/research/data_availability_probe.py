from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from rq_platform.research.report_data_requirements import (
    FieldRequirement,
    derived_requirements,
    load_research_report_requirements,
    raw_probe_requirements,
)
from rq_platform.settings import settings


@dataclass(frozen=True)
class LocalFieldMatch:
    dataset: str
    field: str
    status: str = "available"
    notes: str = ""


LOCAL_FIELD_MAP: dict[str, list[LocalFieldMatch]] = {
    "open": [LocalFieldMatch("prices_1d_none", "open")],
    "high": [LocalFieldMatch("prices_1d_none", "high")],
    "low": [LocalFieldMatch("prices_1d_none", "low")],
    "close": [LocalFieldMatch("prices_1d_none", "close")],
    "volume": [LocalFieldMatch("prices_1d_none", "volume")],
    "total_turnover": [LocalFieldMatch("prices_1d_none", "total_turnover")],
    "limit_up": [LocalFieldMatch("prices_1d_none", "limit_up")],
    "limit_down": [LocalFieldMatch("prices_1d_none", "limit_down")],
    "prev_close": [LocalFieldMatch("prices_1d_none", "close", "derivable_from_existing", "lag previous trading close by order_book_id")],
    "vwap": [LocalFieldMatch("prices_1d_none", "total_turnover", "derivable_from_existing", "total_turnover / volume")],
    "adjust_factor": [LocalFieldMatch("prices_1d_pre", "close", "derivable_from_existing", "compare adjusted and unadjusted close")],
    "is_limit_up": [LocalFieldMatch("prices_1d_none", "limit_up", "derivable_from_existing", "compare close with limit_up")],
    "is_limit_down": [LocalFieldMatch("prices_1d_none", "limit_down", "derivable_from_existing", "compare close with limit_down")],
    "is_suspended": [LocalFieldMatch("tradability_1d", "is_suspended")],
    "is_st": [LocalFieldMatch("tradability_1d", "is_st")],
    "is_listed": [LocalFieldMatch("tradability_1d", "is_listed")],
    "is_tradable": [LocalFieldMatch("tradability_1d", "can_buy", "derivable_from_existing", "can_buy and can_sell")],
    "board_type": [LocalFieldMatch("instruments", "board_type")],
    "exchange": [LocalFieldMatch("instruments", "exchange")],
    "market_cap": [LocalFieldMatch("valuation_1d", "market_cap")],
    "float_market_cap": [LocalFieldMatch("valuation_1d", "float_market_cap")],
    "circulating_market_cap": [LocalFieldMatch("valuation_1d", "float_market_cap")],
    "turnover_rate": [LocalFieldMatch("valuation_1d", "turnover_rate")],
    "pb": [LocalFieldMatch("valuation_1d", "pb_ratio")],
    "pe": [LocalFieldMatch("valuation_1d", "pe_ratio")],
    "ps": [LocalFieldMatch("valuation_1d", "ps_ratio")],
    "pcf": [LocalFieldMatch("valuation_1d", "pcf_ratio")],
    "total_assets": [LocalFieldMatch("financial_pit_quarterly", "total_assets")],
    "equity_parent": [LocalFieldMatch("financial_pit_quarterly", "equity_parent_company")],
    "total_equity": [LocalFieldMatch("financial_pit_quarterly", "total_equity")],
    "net_profit_parent": [LocalFieldMatch("financial_pit_quarterly", "net_profit_parent_company")],
    "risk_free_rate_1y": [LocalFieldMatch("risk_free_rate", "1Y")],
}

for _industry_field in (
    "sw_l1",
    "sw_l2",
    "sw_l3",
    "citics_l1",
    "citics_l2",
    "citics_l3",
    "csi_l1",
    "csi_l2",
    "financial_label",
    "real_estate_label",
    "technology_label",
    "consumer_label",
    "utilities_label",
    "bank_label",
    "broker_label",
):
    LOCAL_FIELD_MAP.setdefault(
        _industry_field,
        [LocalFieldMatch("industry_classification", "industry_name", "derivable_from_existing", "depends on chosen taxonomy mapping")],
    )


for _index_field in (
    "index_members_000985.XSHG",
    "index_members_000300.XSHG",
    "index_members_000905.XSHG",
    "index_members_000906.XSHG",
    "index_members_000852.XSHG",
    "index_members_000955.XSHG",
    "index_members_000932.XSHG",
    "index_members_000931.XSHG",
):
    LOCAL_FIELD_MAP.setdefault(_index_field, [LocalFieldMatch("index_components", "component_order_book_id")])


DATE_COLUMNS = ("trade_date", "info_date", "date", "listed_date", "month")
SYMBOL_COLUMNS = ("order_book_id", "component_order_book_id")


class LocalDataCatalog:
    def __init__(self, data_root: str | Path | None = None):
        self.data_root = Path(data_root).resolve() if data_root else settings.data_root_path
        self._dataset_cache: dict[str, dict[str, Any]] = {}
        self._field_cache: dict[tuple[str, str], dict[str, Any]] = {}

    def dataset_summary(self, dataset: str) -> dict[str, Any]:
        if dataset not in self._dataset_cache:
            self._dataset_cache[dataset] = self._summarize_dataset(dataset)
        return self._dataset_cache[dataset]

    def field_summary(self, dataset: str, field: str) -> dict[str, Any]:
        key = (dataset, field)
        if key not in self._field_cache:
            self._field_cache[key] = self._summarize_field(dataset, field)
        return self._field_cache[key]

    def _dataset_files(self, dataset: str) -> list[Path]:
        base = self.data_root / dataset
        if base.is_file() and base.suffix == ".parquet":
            return [base]
        if base.is_dir():
            return sorted(base.rglob("*.parquet"))
        single = self.data_root / f"{dataset}.parquet"
        if single.exists():
            return [single]
        return []

    def _summarize_dataset(self, dataset: str) -> dict[str, Any]:
        files = self._dataset_files(dataset)
        if not files:
            return {"dataset": dataset, "exists": False, "files": [], "columns": [], "row_count": 0}
        columns = self._read_schema(files[0])
        row_count = sum(self._count_rows(path) for path in files)
        return {
            "dataset": dataset,
            "exists": True,
            "files": [str(path) for path in files],
            "file_count": len(files),
            "columns": columns,
            "row_count": row_count,
        }

    def _summarize_field(self, dataset: str, field: str) -> dict[str, Any]:
        info = self.dataset_summary(dataset)
        if not info["exists"] or field not in info["columns"]:
            return {
                "dataset": dataset,
                "field": field,
                "exists": False,
                "row_count": 0,
                "non_null_ratio": None,
                "latest_non_null_date": "",
                "first_date": "",
                "latest_date": "",
                "latest_date_non_null_ratio": None,
            }
        files = [Path(path) for path in info["files"]]
        date_col = next((col for col in DATE_COLUMNS if col in info["columns"]), None)
        symbol_col = next((col for col in SYMBOL_COLUMNS if col in info["columns"]), None)
        columns = [field]
        if date_col and date_col not in columns:
            columns.append(date_col)
        if symbol_col and symbol_col not in columns:
            columns.append(symbol_col)
        frames = []
        for path in files:
            try:
                frames.append(pd.read_parquet(path, columns=columns))
            except Exception:
                continue
        if not frames:
            return {
                "dataset": dataset,
                "field": field,
                "exists": True,
                "row_count": info["row_count"],
                "non_null_ratio": None,
                "latest_non_null_date": "",
                "first_date": "",
                "latest_date": "",
                "latest_date_non_null_ratio": None,
            }
        df = pd.concat(frames, ignore_index=True)
        non_null = df[field].notna()
        first_date = latest_date = latest_non_null_date = ""
        latest_date_non_null_ratio = None
        symbol_count = None
        if date_col:
            dates = pd.to_datetime(df[date_col], errors="coerce")
            if dates.notna().any():
                first_date = dates.min().date().isoformat()
                latest = dates.max()
                latest_date = latest.date().isoformat()
                latest_mask = dates == latest
                latest_date_non_null_ratio = float(non_null[latest_mask].mean()) if latest_mask.any() else None
                if non_null.any():
                    latest_non_null_date = dates[non_null].max().date().isoformat()
        if symbol_col:
            symbol_count = int(df[symbol_col].nunique(dropna=True))
        return {
            "dataset": dataset,
            "field": field,
            "exists": True,
            "row_count": int(len(df)),
            "symbol_count": symbol_count,
            "non_null_ratio": float(non_null.mean()) if len(df) else None,
            "latest_non_null_date": latest_non_null_date,
            "first_date": first_date,
            "latest_date": latest_date,
            "latest_date_non_null_ratio": latest_date_non_null_ratio,
        }

    @staticmethod
    def _read_schema(path: Path) -> list[str]:
        try:
            import pyarrow.parquet as pq

            return list(pq.ParquetFile(path).schema.names)
        except Exception:
            return list(pd.read_parquet(path).head(0).columns)

    @staticmethod
    def _count_rows(path: Path) -> int:
        try:
            import pyarrow.parquet as pq

            return int(pq.ParquetFile(path).metadata.num_rows)
        except Exception:
            return int(len(pd.read_parquet(path)))


def is_rqdata_probe_enabled(environ: dict[str, str] | None = None) -> bool:
    environ = environ if environ is not None else os.environ
    return environ.get("ENABLE_RQDATA_PROBE") == "1"


def classify_probe_exception(exc: Exception) -> str:
    text = str(exc).lower()
    if any(token in text for token in ("permission", "not permitted", "unauthorized", "license", "auth")):
        return "permission_required"
    if "quota" in text or "limit" in text:
        return "quota_limited"
    return "error"


def build_research_report_data_availability(
    data_root: str | Path | None = None,
    enable_rqdata_probe: bool | None = None,
    requirements: list[FieldRequirement] | None = None,
) -> dict[str, Any]:
    requirements = requirements or load_research_report_requirements()
    enable_rqdata_probe = is_rqdata_probe_enabled() if enable_rqdata_probe is None else enable_rqdata_probe
    catalog = LocalDataCatalog(data_root)
    raw_rows = [
        _build_raw_availability_row(item, catalog, enable_rqdata_probe)
        for item in raw_probe_requirements(requirements)
    ]
    raw_status_by_field = {
        row["canonical_field"]: row["local_status"]
        for row in raw_rows
    }
    derived_items = derived_requirements(requirements)
    derived_status_by_field = _compute_derived_statuses(derived_items, raw_status_by_field)
    derived_rows = [
        _build_derived_dependency_row(item, {**raw_status_by_field, **derived_status_by_field})
        for item in derived_items
    ]
    return {
        "generated_at": pd.Timestamp.now(tz="Asia/Shanghai").isoformat(),
        "data_root": str(Path(data_root).resolve() if data_root else settings.data_root_path),
        "rqdata_probe_enabled": enable_rqdata_probe,
        "raw_availability": raw_rows,
        "derived_dependency": derived_rows,
    }


def _build_raw_availability_row(
    item: FieldRequirement,
    catalog: LocalDataCatalog,
    enable_rqdata_probe: bool,
) -> dict[str, Any]:
    matches = LOCAL_FIELD_MAP.get(item.canonical_field, [])
    local = _best_local_match(matches, catalog)
    rq_status = "not_probed"
    rq_sample_rows = 0
    rq_error = ""
    if enable_rqdata_probe and local["local_status"] in {"missing", "partial"}:
        rq_probe = probe_rqdata_field(item)
        rq_status = rq_probe["rqdata_status"]
        rq_sample_rows = rq_probe["rqdata_sample_rows"]
        rq_error = rq_probe["rqdata_error"]
    return {
        "priority": item.priority,
        "data_pack": item.data_pack,
        "canonical_field": item.canonical_field,
        "chinese_name": item.chinese_name,
        "field_type": item.field_type,
        "required_frequency": item.required_frequency,
        "recommended_storage_frequency": item.recommended_storage_frequency,
        "local_status": local["local_status"],
        "local_dataset": local["local_dataset"],
        "local_field": local["local_field"],
        "local_row_count": local["local_row_count"],
        "local_symbol_count": local["local_symbol_count"],
        "local_non_null_ratio": local["local_non_null_ratio"],
        "local_latest_non_null_date": local["local_latest_non_null_date"],
        "local_date_range": local["local_date_range"],
        "rqdata_probe_enabled": enable_rqdata_probe,
        "rqdata_status": rq_status,
        "rqdata_candidate_function": item.rqdata_candidate_function,
        "rqdata_candidate_field": item.rqdata_candidate_field,
        "rqdata_sample_rows": rq_sample_rows,
        "rqdata_error": rq_error,
        "recommended_dataset_name": item.recommended_dataset_name or _recommended_dataset_name(item),
        "backfill_priority": item.priority,
        "notes": "; ".join(part for part in (item.notes, local["notes"]) if part),
    }


def _best_local_match(matches: list[LocalFieldMatch], catalog: LocalDataCatalog) -> dict[str, Any]:
    for match in matches:
        summary = catalog.field_summary(match.dataset, match.field)
        if summary["exists"]:
            status = match.status
            latest_ratio = summary.get("latest_date_non_null_ratio")
            if status == "available" and latest_ratio is not None and latest_ratio == 0:
                status = "available_but_latest_not_usable"
            return {
                "local_status": status,
                "local_dataset": match.dataset,
                "local_field": match.field,
                "local_row_count": summary.get("row_count") or 0,
                "local_symbol_count": summary.get("symbol_count"),
                "local_non_null_ratio": summary.get("non_null_ratio"),
                "local_latest_non_null_date": summary.get("latest_non_null_date") or "",
                "local_date_range": _date_range(summary),
                "notes": match.notes,
            }
    return {
        "local_status": "missing",
        "local_dataset": "",
        "local_field": "",
        "local_row_count": 0,
        "local_symbol_count": None,
        "local_non_null_ratio": None,
        "local_latest_non_null_date": "",
        "local_date_range": "",
        "notes": "",
    }


def _build_derived_dependency_row(item: FieldRequirement, raw_status_by_field: dict[str, str]) -> dict[str, Any]:
    dependencies = [_normalize_dependency(dep) for dep in item.required_raw_fields]
    statuses = [raw_status_by_field.get(dep, "missing") for dep in dependencies]
    missing = [dep for dep, status in zip(dependencies, statuses) if status == "missing"]
    stale = [dep for dep, status in zip(dependencies, statuses) if status == "available_but_latest_not_usable"]
    if missing:
        status = "blocked_missing_raw"
    elif stale:
        status = "blocked_latest_not_usable"
    elif dependencies:
        status = "derivable_from_existing"
    else:
        status = "needs_manual_review"
    return {
        "priority": item.priority,
        "data_pack": item.data_pack,
        "derived_field": item.canonical_field,
        "chinese_name": item.chinese_name,
        "required_frequency": item.required_frequency,
        "formula": item.derivation_formula,
        "required_raw_fields": ",".join(dependencies),
        "current_raw_field_status": status,
        "missing_raw_fields": ",".join(missing),
        "recommended_materialization": item.recommended_storage_frequency,
        "notes": item.notes,
    }


def _compute_derived_statuses(items: list[FieldRequirement], base_status: dict[str, str]) -> dict[str, str]:
    statuses = dict(base_status)
    derived_by_field = {item.canonical_field: item for item in items}
    changed = True
    while changed:
        changed = False
        for field, item in derived_by_field.items():
            deps = [_normalize_dependency(dep) for dep in item.required_raw_fields]
            dep_statuses = [statuses.get(dep, "missing") for dep in deps]
            if not deps:
                status = "needs_manual_review"
            elif any(status == "missing" for status in dep_statuses):
                status = "missing"
            elif any(status == "available_but_latest_not_usable" for status in dep_statuses):
                status = "available_but_latest_not_usable"
            else:
                status = "derivable_from_existing"
            if statuses.get(field) != status:
                statuses[field] = status
                changed = True
    return {field: statuses[field] for field in derived_by_field}


def probe_rqdata_field(item: FieldRequirement) -> dict[str, Any]:
    try:
        import rqdatac  # type: ignore

        _ = rqdatac
        return _probe_rqdata_field_with_client(item)
    except Exception as exc:
        return {
            "rqdata_status": classify_probe_exception(exc),
            "rqdata_sample_rows": 0,
            "rqdata_error": _safe_error(exc),
        }


def _probe_rqdata_field_with_client(item: FieldRequirement) -> dict[str, Any]:
    import rqdatac  # type: ignore

    token = os.environ.get("RQDATAC_KEY")
    if token:
        rqdatac.init(username="license", password=token)

    if not item.rqdata_candidate_function:
        return {"rqdata_status": "external_source_required", "rqdata_sample_rows": 0, "rqdata_error": ""}
    if not hasattr(rqdatac, item.rqdata_candidate_function):
        return {"rqdata_status": "function_not_found", "rqdata_sample_rows": 0, "rqdata_error": ""}

    symbols = ["600519.XSHG", "000001.XSHE", "300750.XSHE", "688001.XSHG", "000651.XSHE"]
    start_date = "2025-01-02"
    end_date = "2025-01-06"
    try:
        frame = _run_limited_rqdata_probe(rqdatac, item, symbols, start_date, end_date)
    except Exception as exc:
        return {
            "rqdata_status": classify_probe_exception(exc),
            "rqdata_sample_rows": 0,
            "rqdata_error": _safe_error(exc),
        }
    columns = set(frame.columns) if isinstance(frame, pd.DataFrame) else set()
    expected = item.rqdata_candidate_field
    status = "available" if not expected or expected in columns else "field_not_returned"
    return {"rqdata_status": status, "rqdata_sample_rows": int(len(frame)), "rqdata_error": ""}


def _run_limited_rqdata_probe(
    rqdatac: Any,
    item: FieldRequirement,
    symbols: list[str],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    field = item.rqdata_candidate_field
    if item.rqdata_candidate_function == "get_price":
        result = rqdatac.get_price(
            symbols,
            start_date=start_date,
            end_date=end_date,
            frequency="1d",
            fields=[field],
            adjust_type="none",
            expect_df=True,
        )
        return result if isinstance(result, pd.DataFrame) else pd.DataFrame(result)
    if item.rqdata_candidate_function == "get_factor":
        result = rqdatac.get_factor(
            symbols,
            [field],
            start_date=start_date,
            end_date=end_date,
            expect_df=True,
        )
        return result if isinstance(result, pd.DataFrame) else pd.DataFrame(result)
    if item.rqdata_candidate_function == "get_turnover_rate":
        result = rqdatac.get_turnover_rate(symbols, start_date=start_date, end_date=end_date)
        return result if isinstance(result, pd.DataFrame) else pd.DataFrame(result)
    if item.rqdata_candidate_function == "get_pit_financials_ex":
        result = rqdatac.get_pit_financials_ex(
            order_book_ids=symbols,
            fields=[field],
            start_quarter="2024q4",
            end_quarter="2025q1",
            date=end_date,
            statements="all",
            market="cn",
        )
        return result.reset_index() if isinstance(result, pd.DataFrame) else pd.DataFrame(result)
    return pd.DataFrame()


def _normalize_dependency(dep: str) -> str:
    return dep.split(".")[-1]


def _recommended_dataset_name(item: FieldRequirement) -> str:
    if item.field_type == "derived":
        return f"derived/{item.data_pack}"
    return item.data_pack


def _date_range(summary: dict[str, Any]) -> str:
    first_date = summary.get("first_date") or ""
    latest_date = summary.get("latest_date") or ""
    if first_date and latest_date:
        return f"{first_date} to {latest_date}"
    return ""


def _safe_error(exc: Exception) -> str:
    text = str(exc)
    return text[:300]
