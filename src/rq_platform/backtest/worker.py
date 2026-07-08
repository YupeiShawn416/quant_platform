from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest worker placeholder.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    args = parser.parse_args()

    run_dir = Path("/app/runs/backtests") / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "logs.txt"
    log_path.write_text(
        "\n".join(
            [
                "Backtest worker placeholder.",
                f"run_id={args.run_id}",
                f"timeout_seconds={args.timeout_seconds}",
                f"created_at={datetime.now().isoformat(timespec='seconds')}",
                "Future real backtest engine plugs in here.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
