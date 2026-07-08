import importlib.util
import subprocess
import sys
import zipfile
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEIGHTS_TEMPLATE = PROJECT_ROOT / "templates" / "research_weights_template"


def test_research_weights_template_structure_exists():
    assert WEIGHTS_TEMPLATE.exists()
    for name in ["README.md", "AGENTS.md", "WORKFLOW.md"]:
        assert (WEIGHTS_TEMPLATE / name).exists()
    for name in ["factor.py", "signal.py", "portfolio.py", "package_builder.py"]:
        assert (WEIGHTS_TEMPLATE / "src" / "strategy_research" / name).exists()


def test_research_weights_template_functions_exist():
    factor = _load_module(WEIGHTS_TEMPLATE / "src" / "strategy_research" / "factor.py")
    signal = _load_module(WEIGHTS_TEMPLATE / "src" / "strategy_research" / "signal.py")
    portfolio = _load_module(WEIGHTS_TEMPLATE / "src" / "strategy_research" / "portfolio.py")
    package_builder = _load_module(WEIGHTS_TEMPLATE / "src" / "strategy_research" / "package_builder.py")
    assert callable(factor.compute_factor)
    assert callable(signal.generate_signal)
    assert callable(portfolio.generate_weights)
    assert callable(package_builder.build_strategy_package)


def test_create_research_project_from_template_copies_weights(tmp_path):
    subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "20_create_research_project_from_template.py"),
            "--template",
            "weights",
            "--name",
            "unit_weights_project",
            "--output-dir",
            str(tmp_path),
        ],
        check=True,
        cwd=PROJECT_ROOT,
    )
    project = tmp_path / "unit_weights_project"
    assert (project / "README.md").exists()
    output_files = [path for path in (project / "data" / "output").iterdir() if path.name != ".gitkeep"]
    assert output_files == []


def test_template_package_builder_generates_standard_zip(tmp_path):
    module = _load_module(WEIGHTS_TEMPLATE / "src" / "strategy_research" / "package_builder.py")
    config = {
        "strategy_id": "unit_template",
        "strategy_name": "Unit Template",
        "author": "tester",
        "package_version": "1.0",
        "description": "",
        "run": {
            "run_id": "unit_template_2025",
            "start_date": "2025-01-02",
            "end_date": "2025-01-03",
            "initial_cash": 100000,
            "benchmark": "000300.XSHG",
            "adjust_type": "pre",
            "frequency": "daily",
            "commission_rate": 0.0003,
            "tax_rate": 0.001,
            "slippage_rate": 0.0001,
            "lot_size": 100,
            "price_field": "close",
            "weight_mode": "daily_target",
        },
    }
    weights = pd.DataFrame(
        {
            "trade_date": ["2025-01-02"],
            "order_book_id": ["000001.XSHE"],
            "target_weight": [1.0],
        }
    )
    package = module.build_strategy_package(config, weights, tmp_path / "unit_package.zip")
    with zipfile.ZipFile(package) as archive:
        names = set(archive.namelist())
    assert {"manifest.json", "config.json", "README.md"}.issubset(names)
    assert "weights.csv" in names or "weights.parquet" in names


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module
