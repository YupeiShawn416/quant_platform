from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

import pandas as pd

from rq_platform.backtest.job_manager import REQUIRED_CONFIG_FIELDS
from rq_platform.backtest.package_formats import read_weights_file, validate_weights_df


SUPPORTED_PACKAGE_VERSION = "1.0"
SUPPORTED_MODES = {"weights", "signals", "code"}
ALLOWED_REQUIREMENTS = {
    "pandas",
    "numpy",
    "scipy",
    "scikit-learn",
    "statsmodels",
    "duckdb",
    "pyarrow",
    "joblib",
    "matplotlib",
}
STRATEGY_ID_PATTERN = re.compile(r"^[a-z0-9_-]+$")


class StrategyPackageValidationError(Exception):
    pass


class StrategyPackageValidator:
    def __init__(self, max_package_size_mb: int = 100):
        self.max_package_size_mb = max_package_size_mb

    def validate_zip_path(self, package_path: str | Path) -> dict:
        path = Path(package_path)
        if not path.exists():
            raise StrategyPackageValidationError(f"package not found: {path}")
        if path.suffix != ".zip":
            raise StrategyPackageValidationError("strategy package must be a .zip file")
        max_size = self.max_package_size_mb * 1024 * 1024
        if path.stat().st_size > max_size:
            raise StrategyPackageValidationError(
                f"strategy package exceeds {self.max_package_size_mb}MB limit"
            )
        try:
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                if not names:
                    raise StrategyPackageValidationError("strategy package is empty")
                for name in names:
                    self._validate_zip_member(name)
        except zipfile.BadZipFile as exc:
            raise StrategyPackageValidationError("invalid zip package") from exc
        return {"path": str(path), "files": names, "size_bytes": path.stat().st_size}

    def extract_to_temp_dir(self, package_path: str | Path, temp_root: str | Path) -> Path:
        self.validate_zip_path(package_path)
        target = Path(temp_root).resolve()
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(package_path) as archive:
            for member in archive.infolist():
                self._validate_zip_member(member.filename)
                destination = (target / member.filename).resolve()
                if target not in destination.parents and destination != target:
                    raise StrategyPackageValidationError("zip member escapes extraction dir")
                if member.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source, destination.open("wb") as output:
                        output.write(source.read())
        return target

    def load_manifest(self, package_dir: str | Path) -> dict:
        path = Path(package_dir) / "manifest.json"
        if not path.exists():
            raise StrategyPackageValidationError("strategy package missing manifest.json")
        return json.loads(path.read_text(encoding="utf-8"))

    def load_config(self, package_dir: str | Path) -> dict:
        path = Path(package_dir) / "config.json"
        if not path.exists():
            raise StrategyPackageValidationError("strategy package missing config.json")
        return json.loads(path.read_text(encoding="utf-8"))

    def validate_manifest(self, manifest: dict) -> list[str]:
        if not isinstance(manifest, dict):
            raise StrategyPackageValidationError("manifest must be an object")
        if manifest.get("package_version") != SUPPORTED_PACKAGE_VERSION:
            raise StrategyPackageValidationError("manifest package_version must be '1.0'")
        strategy_id = manifest.get("strategy_id")
        if not isinstance(strategy_id, str) or not STRATEGY_ID_PATTERN.match(strategy_id):
            raise StrategyPackageValidationError("manifest strategy_id is invalid")
        for field in ["strategy_name", "author", "created_at"]:
            if not isinstance(manifest.get(field), str) or not manifest[field].strip():
                raise StrategyPackageValidationError(f"manifest {field} must be a non-empty string")
        if manifest.get("mode") not in SUPPORTED_MODES:
            raise StrategyPackageValidationError("manifest mode must be weights, signals, or code")
        for forbidden in ["path", "command", "shell", "url"]:
            if forbidden in manifest:
                raise StrategyPackageValidationError(f"manifest field not allowed: {forbidden}")
        return []

    def validate_config(self, config: dict, mode: str) -> list[str]:
        if not isinstance(config, dict):
            raise StrategyPackageValidationError("config must be an object")
        missing = [field for field in REQUIRED_CONFIG_FIELDS if field not in config]
        if missing:
            raise StrategyPackageValidationError(f"config missing fields: {', '.join(missing)}")
        if mode == "weights":
            if config.get("mode") not in {None, "weights"}:
                raise StrategyPackageValidationError("weights package config mode must be weights")
            if config.get("weight_mode", "daily_target") not in {"daily_target", "rebalance_only"}:
                raise StrategyPackageValidationError("weight_mode must be daily_target or rebalance_only")
        return []

    def validate_weights_package(
        self, package_dir: str | Path, config: dict
    ) -> tuple[pd.DataFrame, list[str]]:
        package_dir = Path(package_dir).resolve()
        weight_file = config.get("weight_file", "weights.parquet")
        path = (package_dir / weight_file).resolve()
        if package_dir not in path.parents and path != package_dir:
            raise StrategyPackageValidationError("weights file path escapes package dir")
        if not path.exists():
            raise StrategyPackageValidationError(f"weights package missing weight file: {weight_file}")
        try:
            return validate_weights_df(read_weights_file(path), config)
        except Exception as exc:
            raise StrategyPackageValidationError(str(exc)) from exc

    def validate_code_package(self, package_dir: str | Path, config: dict) -> list[str]:
        package_dir = Path(package_dir)
        if not (package_dir / "strategy.py").exists():
            raise StrategyPackageValidationError("code package missing strategy.py")
        requirements = package_dir / "requirements.txt"
        if requirements.exists():
            for raw_line in requirements.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                package = re.split(r"[<>=!~\[]", line, maxsplit=1)[0].strip().lower()
                if package not in ALLOWED_REQUIREMENTS:
                    raise StrategyPackageValidationError(
                        f"requirements package not allowed: {package}"
                    )
        return []

    def _validate_zip_member(self, name: str) -> None:
        path = Path(name)
        if path.is_absolute() or ".." in path.parts:
            raise StrategyPackageValidationError("zip package contains unsafe path")
