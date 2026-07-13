from __future__ import annotations

import json
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from rq_platform.backtest.current_store import CurrentBacktestStore
from rq_platform.backtest.docker_runner import run_backtest_in_docker
from rq_platform.backtest.result_schema import ERROR_JSON, LOGS_TXT
from rq_platform.backtest.result_store import BacktestResultStore
from rq_platform.backtest.run_registry import (
    BacktestRunRegistry,
    build_run_record,
    sanitize_run_id,
)
from rq_platform.backtest.run_store import BacktestRunStore
from rq_platform.backtest.worker import run_worker
from rq_platform.settings import settings


MAX_STRATEGY_CODE_BYTES = 200 * 1024
REQUIRED_CONFIG_FIELDS = [
    "run_id",
    "strategy_name",
    "start_date",
    "end_date",
    "initial_cash",
    "adjust_type",
    "frequency",
    "commission_rate",
    "tax_rate",
    "slippage_rate",
    "lot_size",
    "price_field",
]


class BacktestJobError(ValueError):
    pass


class BacktestJobManager:
    def __init__(self):
        self.jobs_dir = settings.backtest_jobs_dir_path
        self.current_store = CurrentBacktestStore()
        self.registry = BacktestRunRegistry()
        self.run_store = BacktestRunStore()

    def create_job_dir(self, job_id: str | None = None) -> Path:
        job_id = job_id or datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
        job_dir = self._safe_job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir

    def run_backtest(
        self,
        strategy_code: str,
        config: dict,
        strategy_filename: str = "strategy.py",
        submitter: dict[str, str] | None = None,
    ) -> dict:
        self._validate_strategy_code(strategy_code)
        self._validate_strategy_filename(strategy_filename)
        self._validate_config(config)

        job_dir = self.create_job_dir()
        job_id = job_dir.name
        config = dict(config)
        submitter = _normalize_submitter(submitter)
        run_id = self.registry.ensure_unique_run_id(sanitize_run_id(config["run_id"]))
        config["run_id"] = run_id
        strategy_path = job_dir / "strategy.py"
        config_path = job_dir / "config.json"
        strategy_path.write_text(strategy_code, encoding="utf-8")
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

        self.current_store.clear_current()
        try:
            mode = settings.backtest_execution_mode.lower()
            if mode == "local":
                result = run_worker(config_path, strategy_path, job_dir)
                run_dir = Path(result["run_dir"])
            elif mode == "docker":
                run_dir = job_dir / run_id
                run_dir.mkdir(parents=True, exist_ok=True)
                docker_result = run_backtest_in_docker(
                    image=settings.backtest_image,
                    run_id=run_id,
                    data_dir=settings.data_root_path,
                    run_dir=run_dir,
                    config_path=config_path,
                    strategy_path=strategy_path,
                    cpu_limit=settings.backtest_cpu_limit,
                    memory_limit=settings.backtest_memory_limit,
                    timeout_seconds=settings.backtest_timeout_seconds,
                )
                if not docker_result["ok"]:
                    raise RuntimeError(docker_result.get("error") or "docker backtest failed")
            else:
                raise BacktestJobError(f"unsupported backtest execution mode: {mode}")

            self.current_store.set_current_from_run_dir(run_dir)
            summary = self.current_store.read_current_json("summary.json")
            cache_dir = self.run_store.save_result_to_cache(run_id, run_dir)
            self.registry.append(
                build_run_record(
                    run_id=run_id,
                    config=config,
                    summary=summary,
                    mode="code",
                    status="success",
                    result_dir=cache_dir,
                    result_available=True,
                    **submitter,
                )
            )
            return {
                "status": "success",
                "job_id": job_id,
                "run_id": run_id,
                "summary": summary,
                "result_urls": _result_urls(run_id),
            }
        except Exception as exc:
            run_dir = self._write_failure_result(job_dir, run_id, config, exc)
            self.current_store.set_current_from_run_dir(run_dir)
            cache_dir = self.run_store.save_result_to_cache(run_id, run_dir)
            self.registry.append(
                build_run_record(
                    run_id=run_id,
                    config=config,
                    mode="code",
                    status="failed",
                    result_dir=cache_dir,
                    result_available=True,
                    error_message=str(exc),
                    **submitter,
                )
            )
            return {
                "status": "failed",
                "job_id": job_id,
                "run_id": run_id,
                "error": str(exc),
                "result_urls": _result_urls(run_id),
            }

    def _validate_config(self, config: dict) -> None:
        if not isinstance(config, dict):
            raise BacktestJobError("config must be an object")
        missing = [field for field in REQUIRED_CONFIG_FIELDS if field not in config]
        if missing:
            raise BacktestJobError(f"missing backtest config fields: {', '.join(missing)}")

    def _validate_strategy_code(self, strategy_code: str) -> None:
        if not isinstance(strategy_code, str) or not strategy_code.strip():
            raise BacktestJobError("strategy_code must be a non-empty string")
        if len(strategy_code.encode("utf-8")) > MAX_STRATEGY_CODE_BYTES:
            raise BacktestJobError("strategy_code exceeds 200KB limit")

    def _validate_strategy_filename(self, strategy_filename: str) -> None:
        if Path(strategy_filename).name != "strategy.py":
            raise BacktestJobError("strategy filename is fixed to strategy.py in V0")

    def _write_failure_result(
        self, job_dir: Path, run_id: str, config: dict[str, Any], exc: Exception
    ) -> Path:
        store = BacktestResultStore(root=job_dir)
        run_dir = store.create_run_dir(run_id)
        error = {
            "run_id": run_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
        store.write_json(run_dir, ERROR_JSON, error)
        store.write_json(run_dir, "config.json", config)
        logs = [
            "回测失败",
            f"run_id={run_id}",
            f"error_type={type(exc).__name__}",
            f"message={exc}",
            traceback.format_exc(),
        ]
        (run_dir / LOGS_TXT).write_text("\n".join(logs) + "\n", encoding="utf-8")
        return run_dir

    def _safe_job_dir(self, job_id: str) -> Path:
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        path = (self.jobs_dir / job_id).resolve()
        if self.jobs_dir not in path.parents and path != self.jobs_dir:
            raise ValueError(f"path escapes backtest jobs dir: {job_id}")
        return path


def _result_urls(run_id: str) -> dict[str, str]:
    return {
        "detail": f"/backtests/runs/{run_id}",
        "summary": f"/backtests/runs/{run_id}/summary",
        "download": f"/backtests/runs/{run_id}/download",
        "dashboard": f"/ui/backtests/runs/{run_id}",
    }


def _normalize_submitter(submitter: dict[str, str] | None) -> dict[str, str]:
    item = dict(submitter or {})
    researcher_name = item.get("researcher_name") or item.get("submitted_by") or "Admin"
    return {
        "researcher_id": item.get("researcher_id") or "admin",
        "researcher_name": researcher_name,
        "submitted_by": item.get("submitted_by") or researcher_name,
        "client_ip": item.get("client_ip") or "",
        "user_agent": item.get("user_agent") or "",
    }
