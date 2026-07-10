from datetime import datetime, timedelta

from rq_platform.backtest.run_registry import BacktestRunRecord, BacktestRunRegistry, sanitize_run_id


def test_sanitize_run_id_replaces_unsafe_chars():
    assert sanitize_run_id("abc/中文 123") == "abc_123"
    assert sanitize_run_id("../bad") == "bad"


def test_registry_append_list_get_update_and_duplicate(tmp_path):
    registry = BacktestRunRegistry(tmp_path / "registry.jsonl")

    registry.append(
        BacktestRunRecord(
            run_id="demo",
            strategy_name="Demo",
            status="success",
            total_return=0.12,
            result_available=True,
        )
    )

    assert registry.get("demo")["strategy_name"] == "Demo"
    assert registry.list_runs()[0]["run_id"] == "demo"
    assert registry.ensure_unique_run_id("demo") != "demo"

    registry.update("demo", sharpe=1.23)
    assert registry.get("demo")["sharpe"] == 1.23


def test_registry_tolerates_broken_json_and_marks_expired(tmp_path):
    path = tmp_path / "registry.jsonl"
    path.write_text('{"run_id": "old", "result_available": true, "expires_at": "2025-01-01T00:00:00Z"}\nnot-json\n')
    registry = BacktestRunRegistry(path)

    cleaned = registry.cleanup_expired(now=datetime(2025, 1, 2))

    assert cleaned == ["old"]
    assert registry.get("old")["result_expired"] is True
    assert registry.warnings


def test_registry_keeps_future_results_available(tmp_path):
    path = tmp_path / "registry.jsonl"
    future = datetime.utcnow() + timedelta(days=1)
    registry = BacktestRunRegistry(path)
    registry.append(
        {
            "run_id": "future",
            "result_available": True,
            "expires_at": future.replace(microsecond=0).isoformat() + "Z",
        }
    )

    assert registry.cleanup_expired(now=datetime.utcnow()) == []
    assert registry.get("future")["result_available"] is True
