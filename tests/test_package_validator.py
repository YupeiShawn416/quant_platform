import json
import zipfile

import pandas as pd
import pytest

from rq_platform.backtest.package_validator import (
    StrategyPackageValidationError,
    StrategyPackageValidator,
)


def test_valid_weights_package_passes(tmp_path):
    package = _make_package(tmp_path)
    validator = StrategyPackageValidator()
    package_dir = validator.extract_to_temp_dir(package, tmp_path / "extract")
    manifest = validator.load_manifest(package_dir)
    config = validator.load_config(package_dir)

    assert validator.validate_manifest(manifest) == []
    assert validator.validate_config(config, "weights") == []
    weights, warnings = validator.validate_weights_package(package_dir, config)
    assert len(weights) == 1
    assert warnings == []


def test_missing_manifest_raises(tmp_path):
    package = _make_package(tmp_path, include_manifest=False)
    validator = StrategyPackageValidator()
    package_dir = validator.extract_to_temp_dir(package, tmp_path / "extract")

    with pytest.raises(StrategyPackageValidationError, match="manifest"):
        validator.load_manifest(package_dir)


def test_missing_config_raises(tmp_path):
    package = _make_package(tmp_path, include_config=False)
    validator = StrategyPackageValidator()
    package_dir = validator.extract_to_temp_dir(package, tmp_path / "extract")

    with pytest.raises(StrategyPackageValidationError, match="config"):
        validator.load_config(package_dir)


def test_zip_slip_rejected(tmp_path):
    package = tmp_path / "bad.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("../bad.txt", "bad")

    with pytest.raises(StrategyPackageValidationError, match="unsafe"):
        StrategyPackageValidator().validate_zip_path(package)


def test_non_whitelist_requirement_rejected(tmp_path):
    package_dir = tmp_path / "code"
    package_dir.mkdir()
    (package_dir / "strategy.py").write_text("def generate_weights(context, data): return {}\n")
    (package_dir / "requirements.txt").write_text("evil-package\n")

    with pytest.raises(StrategyPackageValidationError, match="not allowed"):
        StrategyPackageValidator().validate_code_package(package_dir, _config(mode="code"))


def test_weights_mode_missing_weights_file_raises(tmp_path):
    package = _make_package(tmp_path, include_weights=False)
    validator = StrategyPackageValidator()
    package_dir = validator.extract_to_temp_dir(package, tmp_path / "extract")

    with pytest.raises(StrategyPackageValidationError, match="weight file"):
        validator.validate_weights_package(package_dir, _config())


def test_weights_file_path_escape_rejected(tmp_path):
    package = _make_package(tmp_path)
    validator = StrategyPackageValidator()
    package_dir = validator.extract_to_temp_dir(package, tmp_path / "extract")
    config = _config()
    config["weight_file"] = "../weights.parquet"

    with pytest.raises(StrategyPackageValidationError, match="escapes package dir"):
        validator.validate_weights_package(package_dir, config)


def test_code_mode_missing_strategy_raises(tmp_path):
    package_dir = tmp_path / "code"
    package_dir.mkdir()

    with pytest.raises(StrategyPackageValidationError, match="strategy.py"):
        StrategyPackageValidator().validate_code_package(package_dir, _config(mode="code"))


def _make_package(tmp_path, include_manifest=True, include_config=True, include_weights=True):
    root = tmp_path / "package"
    root.mkdir()
    if include_manifest:
        (root / "manifest.json").write_text(json.dumps(_manifest()), encoding="utf-8")
    if include_config:
        (root / "config.json").write_text(json.dumps(_config()), encoding="utf-8")
    if include_weights:
        pd.DataFrame(
            [{"trade_date": "2025-01-02", "order_book_id": "AAA.X", "target_weight": 0.5}]
        ).to_parquet(root / "weights.parquet", index=False)
    package = tmp_path / "package.zip"
    with zipfile.ZipFile(package, "w") as archive:
        for path in root.iterdir():
            archive.write(path, arcname=path.name)
    return package


def _manifest(mode="weights"):
    return {
        "package_version": "1.0",
        "strategy_id": "demo_weights",
        "strategy_name": "Demo Weights",
        "author": "tester",
        "mode": mode,
        "created_at": "2026-07-08",
        "description": "",
    }


def _config(mode="weights"):
    return {
        "run_id": "package_test",
        "strategy_name": "Demo Weights",
        "start_date": "2025-01-02",
        "end_date": "2025-01-31",
        "initial_cash": 100000,
        "adjust_type": "pre",
        "frequency": "daily",
        "commission_rate": 0.0003,
        "tax_rate": 0.001,
        "slippage_rate": 0.0001,
        "lot_size": 100,
        "price_field": "close",
        "mode": mode,
        "weight_file": "weights.parquet",
    }
