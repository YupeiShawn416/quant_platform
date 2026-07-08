from __future__ import annotations

import argparse
import json
import traceback
from datetime import datetime
from pathlib import Path

from rq_platform.backtest.daily_engine import DailyBacktestEngine
from rq_platform.backtest.result_schema import ERROR_JSON, LOGS_TXT
from rq_platform.backtest.result_store import BacktestResultStore


def run_worker(config_path: str | Path, strategy_path: str | Path, output_root: str | Path) -> dict:
    config_path = Path(config_path)
    strategy_path = Path(strategy_path)
    output_root = Path(output_root)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["output_root"] = str(output_root)
    engine = DailyBacktestEngine(config=config, strategy_path=strategy_path)
    return engine.run()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a daily backtest worker.")
    parser.add_argument("--config", required=True, help="Path to backtest config.json")
    parser.add_argument("--strategy", required=True, help="Path to strategy.py")
    parser.add_argument("--output-root", default="runs/backtests")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    args = parser.parse_args()

    try:
        result = run_worker(args.config, args.strategy, args.output_root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        _write_failure_result(args.config, args.output_root, exc)
        return 1


def _write_failure_result(config_path: str | Path, output_root: str | Path, exc: Exception) -> None:
    config: dict = {}
    try:
        config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    except Exception:
        config = {}
    run_id = str(config.get("run_id") or f"failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    store = BacktestResultStore(root=output_root)
    run_dir = store.create_run_dir(run_id)
    error = {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "error_type": type(exc).__name__,
        "message": str(exc),
    }
    store.write_json(run_dir, ERROR_JSON, error)
    if config:
        store.write_json(run_dir, "config.json", config)
    logs = [
        "回测失败",
        f"run_id={run_id}",
        f"error_type={type(exc).__name__}",
        f"message={exc}",
        traceback.format_exc(),
    ]
    (run_dir / LOGS_TXT).write_text("\n".join(logs) + "\n", encoding="utf-8")
    print(json.dumps(error, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
