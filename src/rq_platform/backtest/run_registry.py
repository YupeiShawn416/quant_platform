from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from rq_platform.settings import settings


SAFE_RUN_ID_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def sanitize_run_id(value: Any) -> str:
    raw = str(value or "").strip()
    clean = SAFE_RUN_ID_RE.sub("_", raw).strip("._-")
    return clean or f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"


@dataclass
class BacktestRunRecord:
    run_id: str
    strategy_name: str | None = None
    mode: str | None = None
    status: str = "unknown"
    created_at: str | None = None
    updated_at: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    initial_cash: float | int | None = None
    benchmark: str | None = None
    total_return: float | None = None
    annual_return: float | None = None
    sharpe: float | None = None
    max_drawdown: float | None = None
    benchmark_return: float | None = None
    excess_return: float | None = None
    trade_count: int | None = None
    result_dir: str | None = None
    result_available: bool = False
    result_expired: bool = False
    expires_at: str | None = None
    error_message: str | None = None
    package_name: str | None = None
    submitted_by: str = "unknown"
    researcher_id: str = "unknown"
    researcher_name: str = "unknown"
    client_ip: str | None = None
    user_agent: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BacktestRunRegistry:
    def __init__(self, path: str | Path | None = None):
        self.path = (
            Path(path).resolve()
            if path is not None
            else settings.backtest_run_registry_path_obj
        )
        self.warnings: list[str] = []

    def append(self, record: BacktestRunRecord | dict[str, Any]) -> dict[str, Any]:
        item = record.to_dict() if isinstance(record, BacktestRunRecord) else dict(record)
        now = utc_now_iso()
        item.setdefault("created_at", now)
        item.setdefault("updated_at", now)
        item["run_id"] = sanitize_run_id(item.get("run_id"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
        return item

    def list_runs(
        self,
        limit: int = 50,
        status: str | None = None,
        researcher_id: str | None = None,
        researcher_name: str | None = None,
        include_expired: bool = True,
    ) -> list[dict[str, Any]]:
        records = self._latest_records()
        items = sorted(records.values(), key=lambda row: row.get("created_at") or "", reverse=True)
        if status:
            items = [item for item in items if item.get("status") == status]
        if researcher_id:
            items = [item for item in items if item.get("researcher_id") == researcher_id]
        if researcher_name:
            needle = researcher_name.lower()
            items = [item for item in items if needle in str(item.get("researcher_name") or "").lower()]
        if not include_expired:
            items = [item for item in items if not item.get("result_expired")]
        return items[:limit]

    def get(self, run_id: str) -> dict[str, Any] | None:
        return self._latest_records().get(sanitize_run_id(run_id))

    def update(self, run_id: str, **fields: Any) -> dict[str, Any]:
        run_id = sanitize_run_id(run_id)
        records = self._latest_records()
        if run_id not in records:
            raise KeyError(run_id)
        records[run_id].update(fields)
        records[run_id]["updated_at"] = utc_now_iso()
        self._rewrite(records.values())
        return records[run_id]

    def mark_result_expired(self, run_id: str) -> dict[str, Any]:
        return self.update(run_id, result_available=False, result_expired=True)

    def cleanup_expired(self, now: datetime | None = None) -> list[str]:
        current = now or datetime.utcnow()
        cleaned: list[str] = []
        for record in self.list_runs(limit=100000):
            expires_at = _parse_iso_datetime(record.get("expires_at"))
            if (
                expires_at is not None
                and expires_at <= current
                and record.get("result_available")
            ):
                self.mark_result_expired(record["run_id"])
                cleaned.append(record["run_id"])
        return cleaned

    def ensure_unique_run_id(self, run_id: str) -> str:
        base = sanitize_run_id(run_id)
        if self.get(base) is None:
            return base
        suffix = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:6]
        return f"{base}_{suffix}"

    def records(self) -> list[dict[str, Any]]:
        return list(self._iter_records())

    def researcher_usage(self) -> dict[str, dict[str, Any]]:
        usage: dict[str, dict[str, Any]] = {}
        for item in self._latest_records().values():
            researcher_id = str(item.get("researcher_id") or item.get("submitted_by") or "unknown")
            name = str(item.get("researcher_name") or item.get("submitted_by") or researcher_id)
            row = usage.setdefault(
                researcher_id,
                {
                    "researcher_id": researcher_id,
                    "name": name,
                    "total_runs": 0,
                    "success_runs": 0,
                    "failed_runs": 0,
                    "last_used_at": None,
                },
            )
            row["name"] = name
            row["total_runs"] += 1
            if item.get("status") == "success":
                row["success_runs"] += 1
            if item.get("status") == "failed":
                row["failed_runs"] += 1
            used_at = item.get("created_at") or item.get("updated_at")
            if used_at and (not row["last_used_at"] or str(used_at) > str(row["last_used_at"])):
                row["last_used_at"] = used_at
        return usage

    def _latest_records(self) -> dict[str, dict[str, Any]]:
        records: dict[str, dict[str, Any]] = {}
        for item in self._iter_records():
            run_id = sanitize_run_id(item.get("run_id"))
            item["run_id"] = run_id
            records[run_id] = item
        return records

    def _iter_records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as file:
            for line_no, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    self.warnings.append(f"broken registry json line: {line_no}")
                    continue
                if isinstance(data, dict) and data.get("run_id"):
                    records.append(data)
        return records

    def _rewrite(self, records: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            for record in records:
                file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def build_run_record(
    *,
    run_id: str,
    config: dict[str, Any] | None = None,
    summary: dict[str, Any] | None = None,
    mode: str | None = None,
    status: str,
    result_dir: str | Path | None = None,
    result_available: bool = False,
    error_message: str | None = None,
    package_name: str | None = None,
    submitted_by: str = "unknown",
    researcher_id: str = "unknown",
    researcher_name: str = "unknown",
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> BacktestRunRecord:
    config = config or {}
    summary = summary or {}
    now = utc_now_iso()
    expires_at = datetime.utcnow() + timedelta(hours=settings.backtest_result_ttl_hours)
    return BacktestRunRecord(
        run_id=sanitize_run_id(run_id),
        strategy_name=summary.get("strategy_name") or config.get("strategy_name"),
        mode=mode,
        status=status,
        created_at=summary.get("created_at") or now,
        updated_at=now,
        start_date=summary.get("start_date") or config.get("start_date"),
        end_date=summary.get("end_date") or config.get("end_date"),
        initial_cash=summary.get("initial_cash") or config.get("initial_cash"),
        benchmark=summary.get("benchmark") or config.get("benchmark"),
        total_return=summary.get("total_return"),
        annual_return=summary.get("annual_return"),
        sharpe=summary.get("sharpe"),
        max_drawdown=summary.get("max_drawdown"),
        benchmark_return=summary.get("benchmark_return"),
        excess_return=summary.get("excess_return"),
        trade_count=summary.get("trade_count"),
        result_dir=str(result_dir) if result_dir is not None else None,
        result_available=result_available,
        result_expired=not result_available,
        expires_at=expires_at.replace(microsecond=0).isoformat() + "Z",
        error_message=error_message,
        package_name=package_name,
        submitted_by=submitted_by,
        researcher_id=researcher_id,
        researcher_name=researcher_name,
        client_ip=client_ip,
        user_agent=user_agent,
    )


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).removesuffix("Z")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None
