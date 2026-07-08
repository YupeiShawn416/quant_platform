from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_MAP = {
    "weights": PROJECT_ROOT / "templates" / "research_weights_template",
    "factor": PROJECT_ROOT / "templates" / "research_factor_template",
    "code": PROJECT_ROOT / "templates" / "strategy_code_template",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a research project from a template.")
    parser.add_argument("--template", choices=sorted(TEMPLATE_MAP), required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    project_name = _normalize_name(args.name)
    source = TEMPLATE_MAP[args.template]
    target = Path(args.output_dir).expanduser().resolve() / project_name
    if target.exists():
        if not args.force:
            raise SystemExit(f"target already exists: {target}; pass --force to overwrite")
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=_ignore_generated_outputs)
    _replace_demo_names(target, args.template, project_name)
    print(target)
    return 0


def _normalize_name(name: str) -> str:
    value = re.sub(r"[^a-z0-9_-]+", "_", name.strip().lower())
    value = re.sub(r"_+", "_", value).strip("_-")
    if not value:
        raise SystemExit("--name cannot be empty")
    return value


def _ignore_generated_outputs(directory: str, names: list[str]) -> set[str]:
    path = Path(directory)
    if path.name == "output" and "data" in path.parts:
        return {name for name in names if name != ".gitkeep"}
    return set()


def _replace_demo_names(project_dir: Path, template: str, project_name: str) -> None:
    replacements = {
        "demo_weights_template": project_name,
        "Demo Weights Template Strategy": project_name.replace("_", " ").title(),
        "demo_factor": project_name,
        "demo_code_template": project_name,
    }
    for path in project_dir.rglob("*"):
        if not path.is_file() or path.suffix not in {".md", ".yaml", ".json", ".py", ".toml", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8")
        updated = text
        for old, new in replacements.items():
            updated = updated.replace(old, new)
        if template == "weights":
            updated = updated.replace("/tmp/demo_weights_template_package.zip", f"/tmp/{project_name}_package.zip")
        if updated != text:
            path.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
