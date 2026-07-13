from __future__ import annotations

import json
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from rq_platform.backtest.current_store import CurrentBacktestStore
from rq_platform.backtest.daily_engine import DailyBacktestEngine
from rq_platform.backtest.job_manager import BacktestJobManager
from rq_platform.backtest.package_validator import (
    StrategyPackageValidationError,
    StrategyPackageValidator,
)
from rq_platform.backtest.result_schema import ERROR_JSON, LOGS_TXT
from rq_platform.backtest.result_store import BacktestResultStore
from rq_platform.backtest.run_registry import (
    BacktestRunRegistry,
    build_run_record,
    sanitize_run_id,
)
from rq_platform.backtest.run_store import BacktestRunStore
from rq_platform.backtest.weight_strategy import WeightFileStrategy
from rq_platform.settings import settings


class StrategyPackageJobManager:
    def __init__(self):
        self.jobs_dir = settings.backtest_jobs_dir_path
        self.current_store = CurrentBacktestStore()
        self.validator = StrategyPackageValidator()
        self.registry = BacktestRunRegistry()
        self.run_store = BacktestRunStore()

    def run_package(self, package_path: str | Path, submitter: dict[str, str] | None = None) -> dict:
        job_dir = self._create_job_dir()
        job_id = job_dir.name
        package_dir = job_dir / "package"
        submitter = _normalize_submitter(submitter)
        try:
            self.validator.extract_to_temp_dir(package_path, package_dir)
            manifest = self.validator.load_manifest(package_dir)
            self.validator.validate_manifest(manifest)
            mode = manifest["mode"]
            config = self.validator.load_config(package_dir)
            self.validator.validate_config(config, mode)
            run_id = self.registry.ensure_unique_run_id(sanitize_run_id(config["run_id"]))
            config["run_id"] = run_id

            if mode == "weights":
                weights_df, warnings = self.validator.validate_weights_package(package_dir, config)
                result = self._run_weights_package(job_dir, config, weights_df)
                self.current_store.set_current_from_run_dir(Path(result["run_dir"]))
                summary = self.current_store.read_current_json("summary.json")
                cache_dir = self.run_store.save_result_to_cache(run_id, result["run_dir"])
                self.registry.append(
                    build_run_record(
                        run_id=run_id,
                        config=config,
                        summary=summary,
                        mode=mode,
                        status="success",
                        result_dir=cache_dir,
                        result_available=True,
                        package_name=Path(package_path).name,
                        **submitter,
                    )
                )
                return {
                    "status": "success",
                    "job_id": job_id,
                    "run_id": run_id,
                    "mode": mode,
                    "summary": summary,
                    "warnings": warnings,
                    "result_urls": _result_urls(run_id),
                }
            if mode == "code":
                self.validator.validate_code_package(package_dir, config)
                strategy_code = (package_dir / "strategy.py").read_text(encoding="utf-8")
                result = BacktestJobManager().run_backtest(strategy_code, config, submitter=submitter)
                result["mode"] = mode
                result["warnings"] = []
                return result
            raise StrategyPackageValidationError(
                "signals mode spec defined but execution not implemented yet"
            )
        except Exception as exc:
            run_id = self._read_run_id(package_dir) or f"package_failed_{job_id}"
            run_id = self.registry.ensure_unique_run_id(sanitize_run_id(run_id))
            run_dir = self._write_failure_result(job_dir, run_id, exc)
            self.current_store.set_current_from_run_dir(run_dir)
            cache_dir = self.run_store.save_result_to_cache(run_id, run_dir)
            self.registry.append(
                build_run_record(
                    run_id=run_id,
                    config=self._read_config(package_dir),
                    mode=None,
                    status="failed",
                    result_dir=cache_dir,
                    result_available=True,
                    error_message=str(exc),
                    package_name=Path(package_path).name,
                    **submitter,
                )
            )
            return {
                "status": "failed",
                "job_id": job_id,
                "run_id": run_id,
                "mode": None,
                "error": str(exc),
                "warnings": [],
                "result_urls": _result_urls(run_id),
            }

    def _run_weights_package(self, job_dir: Path, config: dict, weights_df):
        config = dict(config)
        config["output_root"] = str(job_dir)
        config["symbols"] = sorted(weights_df["order_book_id"].astype(str).unique().tolist())
        strategy = WeightFileStrategy(
            weights_df=weights_df,
            weight_mode=str(config.get("weight_mode", "daily_target")),
        )
        engine = DailyBacktestEngine(config=config, strategy=strategy)
        return engine.run()

    def _create_job_dir(self) -> Path:
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        job_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
        job_dir = (self.jobs_dir / job_id).resolve()
        if self.jobs_dir not in job_dir.parents and job_dir != self.jobs_dir:
            raise ValueError("job dir escapes backtest jobs root")
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir

    def _read_run_id(self, package_dir: Path) -> str | None:
        config = self._read_config(package_dir)
        run_id = config.get("run_id")
        return str(run_id) if run_id else None

    def _read_config(self, package_dir: Path) -> dict[str, Any]:
        config_path = package_dir / "config.json"
        if not config_path.exists():
            return {}
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_failure_result(self, job_dir: Path, run_id: str, exc: Exception) -> Path:
        store = BacktestResultStore(root=job_dir)
        run_dir = store.create_run_dir(run_id)
        error = {
            "run_id": run_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
        store.write_json(run_dir, ERROR_JSON, error)
        logs = [
            "策略包回测失败",
            f"run_id={run_id}",
            f"error_type={type(exc).__name__}",
            f"message={exc}",
            traceback.format_exc(),
        ]
        (run_dir / LOGS_TXT).write_text("\n".join(logs) + "\n", encoding="utf-8")
        return run_dir


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
