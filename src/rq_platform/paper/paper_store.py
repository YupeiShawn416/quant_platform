from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd

from rq_platform.paper.paper_account import PaperAccount, sanitize_paper_id
from rq_platform.settings import settings


class PaperAccountNotFound(FileNotFoundError):
    pass


class PaperAccountStore:
    def __init__(self, accounts_dir: str | Path | None = None):
        self.accounts_dir = (
            Path(accounts_dir).resolve() if accounts_dir is not None else settings.paper_accounts_dir_path
        )

    def account_dir(self, paper_id: str) -> Path:
        path = (self.accounts_dir / sanitize_paper_id(paper_id)).resolve()
        if not str(path).startswith(str(self.accounts_dir.resolve())):
            raise ValueError("paper_id escapes paper account directory")
        return path

    def create_account(self, account: PaperAccount) -> PaperAccount:
        directory = self.account_dir(account.paper_id)
        directory.mkdir(parents=True, exist_ok=False)
        self.write_account(account)
        self._ensure_csv(directory / "daily_account.csv", ["trade_date", "cash", "market_value", "total_value", "nav"])
        self._ensure_csv(directory / "nav.csv", ["trade_date", "nav", "total_value"])
        self._ensure_csv(
            directory / "positions.csv",
            ["trade_date", "order_book_id", "quantity", "close", "market_value", "weight"],
        )
        self._ensure_csv(
            directory / "trades.csv",
            ["trade_date", "order_book_id", "side", "quantity", "price", "amount", "cost"],
        )
        self._ensure_csv(
            directory / "orders.csv",
            ["trade_date", "order_book_id", "side", "target_quantity", "filled_quantity", "price", "status", "reason"],
        )
        (directory / "logs.jsonl").touch()
        return account

    def write_account(self, account: PaperAccount) -> None:
        directory = self.account_dir(account.paper_id)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "account.json").write_text(
            json.dumps(account.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def read_account(self, paper_id: str) -> PaperAccount:
        path = self.account_dir(paper_id) / "account.json"
        if not path.exists():
            raise PaperAccountNotFound(f"paper account not found: {paper_id}")
        return PaperAccount.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def exists(self, paper_id: str) -> bool:
        return (self.account_dir(paper_id) / "account.json").exists()

    def save_target_weights(self, paper_id: str, frame: pd.DataFrame) -> Path:
        self.read_account(paper_id)
        path = self.account_dir(paper_id) / "target_weights.csv"
        frame.to_csv(path, index=False)
        return path

    def read_csv(self, paper_id: str, filename: str) -> pd.DataFrame:
        path = self._safe_file(paper_id, filename)
        if not path.exists():
            raise PaperAccountNotFound(f"paper file not found: {filename}")
        return pd.read_csv(path)

    def write_csv(self, paper_id: str, filename: str, frame: pd.DataFrame) -> None:
        path = self._safe_file(paper_id, filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)

    def append_csv(self, paper_id: str, filename: str, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        path = self._safe_file(paper_id, filename)
        frame = pd.DataFrame(rows)
        frame.to_csv(path, mode="a", header=not path.exists() or path.stat().st_size == 0, index=False)

    def append_log(self, paper_id: str, event: dict[str, Any]) -> None:
        path = self._safe_file(paper_id, "logs.jsonl")
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def read_logs(self, paper_id: str) -> list[dict[str, Any]]:
        path = self._safe_file(paper_id, "logs.jsonl")
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    rows.append({"message": line.strip()})
        return rows

    def package_zip(self, paper_id: str) -> Path:
        self.read_account(paper_id)
        directory = self.account_dir(paper_id)
        zip_path = directory / f"paper_account_{sanitize_paper_id(paper_id)}.zip"
        if zip_path.exists():
            zip_path.unlink()
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(directory.iterdir()):
                if path.name == zip_path.name or path.suffix == ".zip" or path.name == ".env":
                    continue
                if path.is_file():
                    archive.write(path, arcname=path.name)
        return zip_path

    def delete(self, paper_id: str) -> bool:
        directory = self.account_dir(paper_id)
        if directory.exists():
            shutil.rmtree(directory)
            return True
        return False

    def _safe_file(self, paper_id: str, filename: str) -> Path:
        if "/" in filename or "\\" in filename or filename.startswith("."):
            raise ValueError("unsafe paper file name")
        path = (self.account_dir(paper_id) / filename).resolve()
        if not str(path).startswith(str(self.account_dir(paper_id))):
            raise ValueError("paper file escapes account directory")
        return path

    def _ensure_csv(self, path: Path, columns: list[str]) -> None:
        if not path.exists():
            pd.DataFrame(columns=columns).to_csv(path, index=False)
