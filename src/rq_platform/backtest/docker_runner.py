from __future__ import annotations

import subprocess
from pathlib import Path


def build_docker_command(
    image: str,
    run_id: str,
    data_dir: str,
    run_dir: str,
    config_path: str | None = None,
    strategy_path: str | None = None,
    cpu_limit: str = "1.0",
    memory_limit: str = "2g",
    timeout_seconds: int = 600,
) -> list[str]:
    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--cpus",
        cpu_limit,
        "--memory",
        memory_limit,
        "--pids-limit",
        "256",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,size=256m",
        "-v",
        f"{data_dir}:/app/data/rqdata:ro",
        "-v",
        f"{run_dir}:/app/runs/backtests/{run_id}:rw",
    ]
    if config_path:
        command.extend(["-v", f"{config_path}:/app/config/config.json:ro"])
    if strategy_path:
        command.extend(["-v", f"{strategy_path}:/app/strategy/strategy.py:ro"])
    command.extend(
        [
            image,
            "python",
            "-m",
            "rq_platform.backtest.worker",
        ]
    )
    if config_path and strategy_path:
        command.extend(
            [
                "--config",
                "/app/config/config.json",
                "--strategy",
                "/app/strategy/strategy.py",
                "--output-root",
                "/app/runs/backtests",
                "--timeout-seconds",
                str(timeout_seconds),
            ]
        )
    else:
        command.extend(
            [
                "--config",
                f"/app/runs/backtests/{run_id}/config.json",
                "--strategy",
                f"/app/runs/backtests/{run_id}/strategy.py",
                "--output-root",
                "/app/runs/backtests",
                "--timeout-seconds",
                str(timeout_seconds),
            ]
        )
    return command


def run_backtest_in_docker(
    image: str,
    run_id: str,
    data_dir: str | Path,
    run_dir: str | Path,
    config_path: str | Path,
    strategy_path: str | Path,
    cpu_limit: str = "1.0",
    memory_limit: str = "2g",
    timeout_seconds: int = 600,
) -> dict:
    command = build_docker_command(
        image=image,
        run_id=run_id,
        data_dir=str(Path(data_dir).resolve()),
        run_dir=str(Path(run_dir).resolve()),
        config_path=str(Path(config_path).resolve()),
        strategy_path=str(Path(strategy_path).resolve()),
        cpu_limit=cpu_limit,
        memory_limit=memory_limit,
        timeout_seconds=timeout_seconds,
    )
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "command": command,
            "error": f"Docker executable not found: {exc}",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "command": command,
            "error": f"Docker backtest timed out after {timeout_seconds} seconds",
        }
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "command": command,
        "error": None if completed.returncode == 0 else "Docker backtest failed",
    }
