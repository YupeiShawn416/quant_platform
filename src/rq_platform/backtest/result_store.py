from __future__ import annotations

import json
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd


class BacktestResultStore:
    def __init__(self, root: str | Path = "runs/backtests"):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def create_run_dir(self, run_id: str | None = None) -> Path:
        run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
        run_dir = self._run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def write_json(self, run_dir: Path, filename: str, data: dict) -> Path:
        path = self._safe_child(run_dir, filename)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def write_csv(self, run_dir: Path, filename: str, df: pd.DataFrame) -> Path:
        path = self._safe_child(run_dir, filename)
        df.to_csv(path, index=False)
        return path

    def read_json(self, run_id: str, filename: str) -> dict:
        path = self._safe_child(self._run_dir(run_id), filename)
        if not path.exists():
            raise FileNotFoundError(path)
        return json.loads(path.read_text(encoding="utf-8"))

    def read_csv(self, run_id: str, filename: str) -> pd.DataFrame:
        path = self._safe_child(self._run_dir(run_id), filename)
        if not path.exists():
            raise FileNotFoundError(path)
        return pd.read_csv(path)

    def read_text(self, run_id: str, filename: str) -> str:
        path = self._safe_child(self._run_dir(run_id), filename)
        if not path.exists():
            raise FileNotFoundError(path)
        return path.read_text(encoding="utf-8")

    def list_runs(self) -> list[dict]:
        runs: list[dict] = []
        for run_dir in sorted(self.root.iterdir()):
            if not run_dir.is_dir():
                continue
            item = {"run_id": run_dir.name, "path": str(run_dir)}
            summary_path = run_dir / "summary.json"
            if summary_path.exists():
                try:
                    item.update(json.loads(summary_path.read_text(encoding="utf-8")))
                except json.JSONDecodeError:
                    item["summary_error"] = "invalid summary.json"
            runs.append(item)
        return runs

    def package_zip(self, run_id: str) -> Path:
        run_dir = self._run_dir(run_id)
        if not run_dir.exists():
            raise FileNotFoundError(run_dir)
        zip_path = run_dir / f"backtest_result_{run_id}.zip"
        with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(run_dir.iterdir()):
                if path.is_file() and path != zip_path:
                    archive.write(path, arcname=f"{run_id}/{path.name}")
        return zip_path

    def _run_dir(self, run_id: str) -> Path:
        return self._safe_child(self.root, run_id)

    def _safe_child(self, parent: Path, child: str | Path) -> Path:
        parent_resolved = Path(parent).resolve()
        path = (parent_resolved / child).resolve()
        if parent_resolved == self.root:
            base = self.root
        else:
            base = parent_resolved
        if base not in path.parents and path != base:
            raise ValueError(f"path escapes result store root: {child}")
        if self.root not in path.parents and path != self.root:
            raise ValueError(f"path escapes result store root: {child}")
        return path
