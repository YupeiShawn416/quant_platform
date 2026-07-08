from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pandas as pd

from rq_platform.settings import settings


class CurrentBacktestNotFound(FileNotFoundError):
    pass


class CurrentBacktestStore:
    def __init__(self, current_dir: str | Path | None = None):
        self.current_dir = (
            Path(current_dir).resolve()
            if current_dir is not None
            else settings.backtest_current_dir_path
        )

    def clear_current(self) -> None:
        if self.current_dir.exists():
            for path in self.current_dir.iterdir():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
        self.current_dir.mkdir(parents=True, exist_ok=True)

    def set_current_from_run_dir(self, run_dir: Path) -> Path:
        run_dir = Path(run_dir).resolve()
        if not run_dir.exists() or not run_dir.is_dir():
            raise FileNotFoundError(f"backtest run dir not found: {run_dir}")
        self.clear_current()
        for source in sorted(run_dir.iterdir()):
            if not source.is_file():
                continue
            if source.name == ".env" or source.name.startswith(".env."):
                continue
            target = self._safe_child(source.name)
            shutil.copy2(source, target)
        return self.current_dir

    def current_exists(self) -> bool:
        return self.current_dir.exists() and any(self.current_dir.iterdir())

    def get_current_dir(self) -> Path:
        if not self.current_exists():
            raise CurrentBacktestNotFound("current backtest result does not exist")
        return self.current_dir

    def read_current_json(self, filename: str) -> dict:
        path = self._existing_child(filename)
        return json.loads(path.read_text(encoding="utf-8"))

    def read_current_csv(self, filename: str) -> pd.DataFrame:
        path = self._existing_child(filename)
        return pd.read_csv(path)

    def read_current_text(self, filename: str) -> str:
        path = self._existing_child(filename)
        return path.read_text(encoding="utf-8")

    def package_current_zip(self) -> Path:
        current_dir = self.get_current_dir()
        zip_path = self._safe_child("current_backtest.zip")
        with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(current_dir.iterdir()):
                if path.is_file() and path != zip_path and not path.name.startswith(".env"):
                    archive.write(path, arcname=f"current/{path.name}")
        return zip_path

    def delete_current(self) -> None:
        if self.current_dir.exists():
            shutil.rmtree(self.current_dir)

    def _existing_child(self, filename: str) -> Path:
        path = self._safe_child(filename)
        if not path.exists():
            raise CurrentBacktestNotFound(f"current backtest file not found: {filename}")
        return path

    def _safe_child(self, filename: str | Path) -> Path:
        path = (self.current_dir / filename).resolve()
        base = self.current_dir.resolve()
        if path != base and base not in path.parents:
            raise ValueError(f"path escapes current backtest dir: {filename}")
        return path
