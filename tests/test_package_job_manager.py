import json
import zipfile

import pandas as pd

import rq_platform.backtest.package_job_manager as package_job_manager
from rq_platform.backtest.current_store import CurrentBacktestStore
from rq_platform.backtest.package_job_manager import StrategyPackageJobManager
from rq_platform.settings import settings


def test_package_job_manager_runs_weights_package(tmp_path, monkeypatch):
    _patch_dirs(tmp_path, monkeypatch)
    package_path = _make_weights_package(tmp_path)

    class FakeEngine:
        def __init__(self, config, strategy=None):
            self.config = config
            self.strategy = strategy

        def run(self):
            run_dir = tmp_path / "jobs" / self.config["run_id"]
            run_dir.mkdir(parents=True)
            (run_dir / "summary.json").write_text(
                json.dumps({"run_id": self.config["run_id"], "total_return": 0.12}),
                encoding="utf-8",
            )
            pd.DataFrame({"trade_date": ["2025-01-02"], "strategy_nav": [1.0]}).to_csv(
                run_dir / "nav.csv", index=False
            )
            pd.DataFrame({"trade_date": ["2025-01-02"], "side": ["BUY"]}).to_csv(
                run_dir / "trades.csv", index=False
            )
            pd.DataFrame({"trade_date": ["2025-01-02"], "quantity": [100]}).to_csv(
                run_dir / "positions.csv", index=False
            )
            (run_dir / "logs.txt").write_text("ok\n", encoding="utf-8")
            return {"run_id": self.config["run_id"], "run_dir": str(run_dir)}

    monkeypatch.setattr(package_job_manager, "DailyBacktestEngine", FakeEngine)

    result = StrategyPackageJobManager().run_package(package_path)

    assert result["status"] == "success"
    assert result["run_id"] == "weights_package_test"
    assert result["mode"] == "weights"
    assert result["summary"]["total_return"] == 0.12
    current_summary = CurrentBacktestStore().read_current_json("summary.json")
    assert current_summary["run_id"] == "weights_package_test"


def test_package_job_manager_invalid_package_writes_current_error(tmp_path, monkeypatch):
    _patch_dirs(tmp_path, monkeypatch)
    package_path = tmp_path / "invalid.zip"
    with zipfile.ZipFile(package_path, "w") as archive:
        archive.writestr("manifest.json", "{}")

    result = StrategyPackageJobManager().run_package(package_path)

    assert result["status"] == "failed"
    assert CurrentBacktestStore().read_current_json("error.json")["error_type"]


def test_package_job_manager_signals_mode_is_explicitly_unimplemented(tmp_path, monkeypatch):
    _patch_dirs(tmp_path, monkeypatch)
    package_dir = tmp_path / "signals_pkg"
    package_dir.mkdir()
    (package_dir / "manifest.json").write_text(
        json.dumps(
            {
                "package_version": "1.0",
                "strategy_id": "signals_demo",
                "strategy_name": "Signals Demo",
                "mode": "signals",
                "created_at": "2026-01-01T00:00:00",
                "author": "test",
            }
        ),
        encoding="utf-8",
    )
    (package_dir / "config.json").write_text(json.dumps(_config("signals_demo")), encoding="utf-8")
    package_path = tmp_path / "signals.zip"
    with zipfile.ZipFile(package_path, "w") as archive:
        for path in package_dir.iterdir():
            archive.write(path, path.name)

    result = StrategyPackageJobManager().run_package(package_path)

    assert result["status"] == "failed"
    assert "signals mode spec defined" in result["error"]


def _make_weights_package(tmp_path):
    package_dir = tmp_path / "weights_pkg"
    package_dir.mkdir()
    (package_dir / "manifest.json").write_text(
        json.dumps(
            {
                "package_version": "1.0",
                "strategy_id": "weights_demo",
                "strategy_name": "Weights Demo",
                "mode": "weights",
                "created_at": "2026-01-01T00:00:00",
                "author": "test",
            }
        ),
        encoding="utf-8",
    )
    (package_dir / "config.json").write_text(
        json.dumps(_config("weights_package_test")),
        encoding="utf-8",
    )
    pd.DataFrame(
        {
            "trade_date": ["2025-01-02", "2025-01-02"],
            "order_book_id": ["AAA.X", "BBB.X"],
            "target_weight": [0.5, 0.5],
        }
    ).to_csv(package_dir / "weights.csv", index=False)
    package_path = tmp_path / "weights.zip"
    with zipfile.ZipFile(package_path, "w") as archive:
        for path in package_dir.iterdir():
            archive.write(path, path.name)
    return package_path


def _config(run_id):
    return {
        "run_id": run_id,
        "strategy_name": "package_unit_strategy",
        "start_date": "2025-01-02",
        "end_date": "2025-01-06",
        "initial_cash": 100000.0,
        "benchmark": "000300.XSHG",
        "adjust_type": "pre",
        "frequency": "daily",
        "commission_rate": 0.0003,
        "tax_rate": 0.001,
        "slippage_rate": 0.0001,
        "lot_size": 100,
        "price_field": "close",
        "mode": "weights",
        "weight_mode": "daily_target",
        "weight_file": "weights.csv",
    }


def _patch_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backtest_current_dir", str(tmp_path / "current"))
    monkeypatch.setattr(settings, "backtest_jobs_dir", str(tmp_path / "jobs"))
