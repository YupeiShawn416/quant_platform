from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping, Protocol, Sequence

from dotenv import dotenv_values

from factor_pool.config import PROJECT_ROOT


class CredentialMissingError(RuntimeError):
    pass


class RQDataProtocol(Protocol):
    __version__: str

    def init(self, **kwargs): ...

    def get_all_factor_names(self, type=None, market="cn"): ...


@dataclass(frozen=True)
class Credential:
    secret: str
    source: str


def resolve_credential(
    environment: Mapping[str, str] | None = None,
    env_path: Path | None = None,
) -> Credential:
    values = os.environ if environment is None else environment
    if values.get("RQDATAC_KEY"):
        return Credential(values["RQDATAC_KEY"], "environment:RQDATAC_KEY")
    if values.get("RQDATA_HTTP_TOKEN"):
        return Credential(values["RQDATA_HTTP_TOKEN"], "environment:RQDATA_HTTP_TOKEN")

    dotenv_path = env_path or PROJECT_ROOT / ".env"
    if dotenv_path.is_file():
        secret = dotenv_values(dotenv_path).get("RQDATAC_KEY")
        if secret:
            return Credential(str(secret), "dotenv:RQDATAC_KEY")
    raise CredentialMissingError("RQData credential missing; set RQDATAC_KEY")


class RQDataAdapter:
    def __init__(
        self,
        *,
        credential: str,
        market: str = "cn",
        credential_source: str = "injected",
        sdk: RQDataProtocol | None = None,
    ) -> None:
        if sdk is None:
            import rqdatac as sdk_module

            sdk = sdk_module
        self._sdk = sdk
        self._credential = credential
        self._credential_source = credential_source
        self.market = market
        self._authenticated = False

    @property
    def sdk_version(self) -> str:
        return str(self._sdk.__version__)

    def authenticate(self) -> None:
        if self._authenticated:
            return
        self._sdk.init(username="license", password=self._credential, lazy=False)
        self._authenticated = True

    def enumerate_fields(self, categories: Sequence[str]) -> list[dict[str, str]]:
        self.authenticate()
        records: list[dict[str, str]] = []
        for category in categories:
            names = self._sdk.get_all_factor_names(type=category, market=self.market)
            if not isinstance(names, (list, tuple)):
                raise TypeError(f"RQData enumeration returned invalid type for category {category}")
            records.extend(
                {"vendor_field_name": name, "vendor_category": category}
                for name in names
            )
        return records

    def capabilities(self, *, field_count: int) -> dict[str, object]:
        return {
            "provider": "RQData",
            "market": self.market,
            "rqdatac_version": self.sdk_version,
            "authenticated": self._authenticated,
            "credential_source": self._credential_source,
            "field_enumeration_supported": True,
            "field_count": field_count,
            "sample_query_supported": True,
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }


def create_adapter_from_environment(*, market: str = "cn") -> RQDataAdapter:
    credential = resolve_credential()
    return RQDataAdapter(
        credential=credential.secret,
        credential_source=credential.source,
        market=market,
    )

