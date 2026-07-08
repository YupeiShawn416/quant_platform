import subprocess

from rq_platform.backtest.docker_runner import build_docker_command, run_backtest_in_docker


def test_docker_command_contains_sandbox_limits():
    command = build_docker_command(
        image="quant-backtest:latest",
        run_id="demo_run",
        data_dir="/data/rqdata",
        run_dir="/runs/demo_run",
    )
    joined = " ".join(command)

    assert "--network none" in joined
    assert "--memory 2g" in joined
    assert "--cpus 1.0" in joined
    assert "/data/rqdata:/app/data/rqdata:ro" in command
    assert "/runs/demo_run:/app/runs/backtests/demo_run:rw" in command
    assert ".env" not in joined


def test_docker_command_mounts_config_and_strategy_readonly():
    command = build_docker_command(
        image="quant-backtest:latest",
        run_id="demo_run",
        data_dir="/data/rqdata",
        run_dir="/runs/demo_run",
        config_path="/strategies/config.json",
        strategy_path="/strategies/strategy.py",
    )

    assert "/strategies/config.json:/app/config/config.json:ro" in command
    assert "/strategies/strategy.py:/app/strategy/strategy.py:ro" in command
    assert "--network none" in " ".join(command)


def test_run_backtest_in_docker_captures_subprocess(monkeypatch, tmp_path):
    def fake_run(command, capture_output, text, timeout, check):
        assert capture_output is True
        assert text is True
        assert check is False
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = run_backtest_in_docker(
        image="quant-backtest:latest",
        run_id="demo_run",
        data_dir=tmp_path / "data",
        run_dir=tmp_path / "run",
        config_path=tmp_path / "config.json",
        strategy_path=tmp_path / "strategy.py",
    )

    assert result["ok"] is True
    assert result["stdout"] == "ok"
