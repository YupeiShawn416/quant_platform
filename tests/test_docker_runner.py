from rq_platform.backtest.docker_runner import build_docker_command


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
