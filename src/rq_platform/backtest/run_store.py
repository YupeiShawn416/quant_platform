from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pandas as pd

from rq_platform.backtest.run_registry import sanitize_run_id
from rq_platform.settings import settings


class BacktestRunResultNotFound(FileNotFoundError):
    pass


class BacktestRunStore:
    def __init__(self, cache_root: str | Path | None = None):
        self.cache_root = (
            Path(cache_root).resolve()
            if cache_root is not None
            else settings.backtest_run_cache_dir_path
        )

    def get_cache_dir(self, run_id: str) -> Path:
        run_id = sanitize_run_id(run_id)
        return self._safe_child(run_id)

    def save_result_to_cache(self, run_id: str, result_dir: str | Path) -> Path:
        source_dir = Path(result_dir).resolve()
        if not source_dir.exists() or not source_dir.is_dir():
            raise FileNotFoundError(f"backtest result dir not found: {source_dir}")
        target_dir = self.get_cache_dir(run_id)
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        for source in sorted(source_dir.iterdir()):
            if not source.is_file():
                continue
            if source.name == ".env" or source.name.startswith(".env."):
                continue
            shutil.copy2(source, self._safe_file(target_dir, source.name))
        return target_dir

    def result_available(self, run_id: str) -> bool:
        cache_dir = self.get_cache_dir(run_id)
        return cache_dir.exists() and any(cache_dir.iterdir())

    def read_json(self, run_id: str, filename: str) -> dict:
        path = self._existing_file(run_id, filename)
        return json.loads(path.read_text(encoding="utf-8"))

    def read_csv(self, run_id: str, filename: str) -> pd.DataFrame:
        path = self._existing_file(run_id, filename)
        return pd.read_csv(path)

    def read_text(self, run_id: str, filename: str) -> str:
        path = self._existing_file(run_id, filename)
        return path.read_text(encoding="utf-8")

    def package_zip(self, run_id: str) -> Path:
        run_id = sanitize_run_id(run_id)
        cache_dir = self.get_cache_dir(run_id)
        if not self.result_available(run_id):
            raise BacktestRunResultNotFound(f"run result files not available: {run_id}")
        zip_path = self._safe_file(cache_dir, f"backtest_result_{run_id}.zip")
        with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(cache_dir.iterdir()):
                if path.is_file() and path != zip_path and not path.name.startswith(".env"):
                    archive.write(path, arcname=f"{run_id}/{path.name}")
        return zip_path

    def delete_cache(self, run_id: str) -> bool:
        cache_dir = self.get_cache_dir(run_id)
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            return True
        return False

    def _existing_file(self, run_id: str, filename: str) -> Path:
        cache_dir = self.get_cache_dir(run_id)
        if not self.result_available(run_id):
            raise BacktestRunResultNotFound(f"run result files not available: {run_id}")
        path = self._safe_file(cache_dir, filename)
        if not path.exists():
            raise BacktestRunResultNotFound(f"run result file not found: {filename}")
        return path

    def _safe_child(self, child: str | Path) -> Path:
        path = (self.cache_root / child).resolve()
        base = self.cache_root.resolve()
        if path != base and base not in path.parents:
            raise ValueError(f"path escapes run cache dir: {child}")
        return path

    def _safe_file(self, parent: Path, filename: str | Path) -> Path:
        parent = Path(parent).resolve()
        path = (parent / filename).resolve()
        if parent not in path.parents and path != parent:
            raise ValueError(f"path escapes run result dir: {filename}")
        if self.cache_root.resolve() not in path.parents:
            raise ValueError(f"path escapes run cache dir: {filename}")
        return path
