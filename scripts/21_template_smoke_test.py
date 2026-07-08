from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = Path("/tmp/smoke_weights_project")
STEPS = [
    "scripts/01_load_data.py",
    "scripts/02_compute_factor.py",
    "scripts/03_generate_signal.py",
    "scripts/04_generate_weights.py",
    "scripts/05_validate_outputs.py",
    "scripts/06_build_package.py",
]


def main() -> int:
    create = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "20_create_research_project_from_template.py"),
        "--template",
        "weights",
        "--name",
        PROJECT_DIR.name,
        "--output-dir",
        str(PROJECT_DIR.parent),
        "--force",
    ]
    subprocess.run(create, cwd=PROJECT_ROOT, check=True)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PROJECT_DIR / "src")
    for step in STEPS:
        subprocess.run([sys.executable, step], cwd=PROJECT_DIR, env=env, check=True)
    package_path = Path("/tmp/smoke_weights_project_package.zip")
    if not package_path.exists():
        raise SystemExit(f"template smoke did not create package: {package_path}")
    output_dir = PROJECT_DIR / "data" / "output"
    generated = sorted(path.name for path in output_dir.iterdir() if path.name != ".gitkeep")
    print(f"template smoke package={package_path}")
    print(f"template smoke generated={generated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
