from __future__ import annotations

import sys
from pathlib import Path

from rq_platform.settings import settings


def main() -> int:
    failures = 0

    _ok(f"Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    _ok(f"current working directory: {Path.cwd()}")

    data_root = settings.data_root_path
    failures += _check_path(data_root, f"data root exists: {data_root}", critical=True)
    failures += _check_path(
        data_root / "instruments" / "instruments.parquet",
        "instruments parquet exists",
        critical=True,
    )
    failures += _check_path(
        data_root / "trading_calendar" / "trading_calendar.parquet",
        "trading calendar parquet exists",
        critical=True,
    )
    failures += _check_path(
        data_root / "prices_1d_pre" / "year=2025.parquet",
        "prices_1d_pre 2025 parquet exists",
        critical=True,
    )
    failures += _check_path(
        data_root / "prices_1d_none" / "year=2025.parquet",
        "prices_1d_none 2025 parquet exists",
        critical=True,
    )

    if settings.api_token == "change_me":
        _warn("API_TOKEN is still change_me; production must change it")
    else:
        _ok("API_TOKEN is configured")

    if Path(settings.data_root).is_absolute():
        _ok("DATA_ROOT is absolute")
    else:
        _warn("DATA_ROOT is not absolute; production should use an absolute path")

    try:
        import rq_platform  # noqa: F401
    except Exception as exc:
        _fail(f"import rq_platform failed: {type(exc).__name__}: {exc}")
        failures += 1
    else:
        _ok("import rq_platform")

    return 1 if failures else 0


def _check_path(path: Path, message: str, critical: bool) -> int:
    if path.exists():
        _ok(message)
        return 0
    if critical:
        _fail(message)
        return 1
    _warn(message)
    return 0


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _warn(message: str) -> None:
    print(f"[WARN] {message}")


def _fail(message: str) -> None:
    print(f"[FAIL] {message}")


if __name__ == "__main__":
    raise SystemExit(main())
