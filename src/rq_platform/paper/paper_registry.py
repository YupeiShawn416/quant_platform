from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rq_platform.paper.paper_account import PaperAccount, sanitize_paper_id, utc_now_iso
from rq_platform.settings import settings


class PaperAccountRegistry:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path).resolve() if path is not None else settings.paper_registry_path_obj

    def upsert(self, account: PaperAccount | dict[str, Any]) -> dict[str, Any]:
        item = account.to_dict() if isinstance(account, PaperAccount) else dict(account)
        item["paper_id"] = sanitize_paper_id(item.get("paper_id"))
        item["updated_at"] = utc_now_iso()
        records = self._latest_records()
        records[item["paper_id"]] = item
        self._rewrite(records.values())
        return item

    def get(self, paper_id: str) -> dict[str, Any] | None:
        return self._latest_records().get(sanitize_paper_id(paper_id))

    def list_accounts(
        self,
        *,
        researcher_id: str | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        items = list(self._latest_records().values())
        if researcher_id:
            items = [item for item in items if item.get("researcher_id") == researcher_id]
        if status:
            items = [item for item in items if item.get("status") == status]
        items = sorted(items, key=lambda item: item.get("updated_at") or "", reverse=True)
        return items[:limit]

    def _latest_records(self) -> dict[str, dict[str, Any]]:
        records: dict[str, dict[str, Any]] = {}
        if not self.path.exists():
            return records
        with self.path.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict) and item.get("paper_id"):
                    records[sanitize_paper_id(item["paper_id"])] = item
        return records

    def _rewrite(self, records) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            for record in records:
                file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
