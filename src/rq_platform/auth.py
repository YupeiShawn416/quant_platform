from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rq_platform.settings import settings


@dataclass(frozen=True)
class ResearcherToken:
    researcher_id: str
    name: str
    token_hash: str
    enabled: bool = True
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "researcher_id": self.researcher_id,
            "name": self.name,
            "token_hash": self.token_hash,
            "enabled": self.enabled,
            "note": self.note,
        }


@dataclass(frozen=True)
class AuthContext:
    researcher_id: str
    researcher_name: str
    token_type: str
    enabled: bool = True

    @property
    def submitted_by(self) -> str:
        return self.researcher_name

    def to_metadata(self) -> dict[str, str]:
        return {
            "researcher_id": self.researcher_id,
            "researcher_name": self.researcher_name,
            "submitted_by": self.submitted_by,
        }


def legacy_admin_context() -> AuthContext:
    return AuthContext("admin", "Admin", "legacy_admin")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token(token: str, token_hash: str) -> bool:
    return secrets.compare_digest(hash_token(token), str(token_hash))


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def load_researcher_tokens(path: str | Path | None = None) -> list[ResearcherToken]:
    token_path = Path(path).resolve() if path is not None else settings.researcher_tokens_path_obj
    if not token_path.exists():
        return []
    data = json.loads(token_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("researcher token config must be a list")
    tokens: list[ResearcherToken] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        tokens.append(
            ResearcherToken(
                researcher_id=str(item.get("researcher_id") or "").strip(),
                name=str(item.get("name") or "").strip(),
                token_hash=str(item.get("token_hash") or "").strip(),
                enabled=bool(item.get("enabled", True)),
                note=str(item.get("note") or ""),
            )
        )
    return [token for token in tokens if token.researcher_id and token.name and token.token_hash]


def save_researcher_tokens(tokens: list[ResearcherToken], path: str | Path | None = None) -> Path:
    token_path = Path(path).resolve() if path is not None else settings.researcher_tokens_path_obj
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(
        json.dumps([token.to_dict() for token in tokens], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return token_path


def authenticate_token(token: str, path: str | Path | None = None) -> AuthContext | None:
    if settings.api_token and token == settings.api_token:
        return legacy_admin_context()
    for item in load_researcher_tokens(path):
        if verify_token(token, item.token_hash):
            return AuthContext(
                researcher_id=item.researcher_id,
                researcher_name=item.name,
                token_type="researcher",
                enabled=item.enabled,
            )
    return None
