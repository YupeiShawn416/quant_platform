from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from rq_platform.settings import settings


def append_data_access_log(record: dict[str, Any], path: str | Path | None = None) -> None:
    log_path = Path(path).resolve() if path is not None else settings.data_access_log_path_obj
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"created_at": _utc_now_iso(), **record}
        with log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        return


def _utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
