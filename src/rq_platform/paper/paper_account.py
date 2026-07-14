from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


SAFE_PAPER_ID_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def sanitize_paper_id(value: Any) -> str:
    raw = str(value or "").strip()
    clean = SAFE_PAPER_ID_RE.sub("_", raw).strip("._-")
    return clean or f"paper_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"


@dataclass
class PaperAccount:
    paper_id: str
    strategy_name: str
    researcher_id: str
    researcher_name: str
    initial_cash: float
    benchmark: str | None = None
    status: str = "active"
    created_at: str | None = None
    updated_at: str | None = None
    latest_trade_date: str | None = None
    current_nav: float = 1.0
    total_return: float = 0.0
    max_drawdown: float = 0.0
    cash: float | None = None

    def __post_init__(self) -> None:
        self.paper_id = sanitize_paper_id(self.paper_id)
        now = utc_now_iso()
        self.created_at = self.created_at or now
        self.updated_at = self.updated_at or now
        if self.cash is None:
            self.cash = float(self.initial_cash)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PaperAccount":
        return cls(
            paper_id=data["paper_id"],
            strategy_name=data.get("strategy_name") or data["paper_id"],
            researcher_id=data.get("researcher_id") or "unknown",
            researcher_name=data.get("researcher_name") or "unknown",
            initial_cash=float(data.get("initial_cash") or 0),
            benchmark=data.get("benchmark"),
            status=data.get("status") or "active",
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            latest_trade_date=data.get("latest_trade_date"),
            current_nav=float(data.get("current_nav") or 1.0),
            total_return=float(data.get("total_return") or 0.0),
            max_drawdown=float(data.get("max_drawdown") or 0.0),
            cash=float(data["cash"]) if data.get("cash") is not None else None,
        )
