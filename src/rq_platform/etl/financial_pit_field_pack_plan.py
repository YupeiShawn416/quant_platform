from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from rq_platform.settings import settings


DEFAULT_PROBE_CSV = Path("reports/generated/research_report_p0_rqdata_probe.csv")
DEFAULT_SYMBOLS = [
    "000001.XSHE",
    "000002.XSHE",
    "600000.XSHG",
    "600519.XSHG",
    "300750.XSHE",
    "688981.XSHG",
]


@dataclass(frozen=True)
class FinancialPitField:
    canonical_field: str
    rqdata_function: str
    rqdata_field: str


@dataclass(frozen=True)
class FinancialPitFieldPackTask:
    start_date: str
    end_date: str
    start_quarter: str
    end_quarter: str
    symbols: list[str]
    fields: list[FinancialPitField]
    batch_size: int
    dry_run: bool
    overwrite: bool

    @property
    def expected_api_calls(self) -> int:
        return max(1, (len(self.symbols) + self.batch_size - 1) // self.batch_size)


def load_available_financial_pit_fields(
    probe_csv: str | Path = DEFAULT_PROBE_CSV,
    fields: list[str] | None = None,
) -> list[FinancialPitField]:
    path = Path(probe_csv)
    if not path.exists():
        raise FileNotFoundError(f"Stage 33B probe report not found: {path}")
    frame = pd.read_csv(path).fillna("")
    filtered = frame[
        (frame["data_pack"] == "financial_pit_core")
        & (frame["rqdata_probe_status"] == "available")
        & (frame["field_type"].isin(["raw", "label", "event", "metadata"]))
    ].copy()
    if fields:
        requested = set(fields)
        filtered = filtered[filtered["canonical_field"].isin(requested)]
    filtered = filtered.sort_values("canonical_field")
    return [
        FinancialPitField(
            canonical_field=str(row["canonical_field"]),
            rqdata_function=str(row["rqdata_candidate_function"]),
            rqdata_field=str(row["rqdata_candidate_field"]),
        )
        for row in filtered.to_dict(orient="records")
    ]


def load_a_share_symbols(data_root: str | Path | None = None) -> list[str]:
    root = Path(data_root).resolve() if data_root is not None else settings.data_root_path
    path = root / "instruments.parquet"
    if not path.exists():
        path = root / "instruments" / "instruments.parquet"
    if not path.exists():
        return []
    frame = pd.read_parquet(path)
    if "order_book_id" not in frame.columns:
        return []
    symbols = frame["order_book_id"].astype(str)
    symbols = symbols[symbols.str.endswith((".XSHG", ".XSHE"))]
    return sorted(symbols.unique().tolist())


def parse_symbols(symbols: str | None) -> list[str]:
    if not symbols:
        return DEFAULT_SYMBOLS.copy()
    return [item.strip() for item in symbols.split(",") if item.strip()]


def build_financial_pit_field_pack_task(
    *,
    start_date: str,
    end_date: str,
    symbols: list[str] | None,
    fields: list[FinancialPitField],
    batch_size: int,
    dry_run: bool,
    overwrite: bool,
) -> FinancialPitFieldPackTask:
    if not fields:
        raise ValueError("No Stage 33B verified financial_pit_core fields are available for backfill.")
    final_symbols = symbols if symbols is not None else load_a_share_symbols()
    if not final_symbols:
        raise ValueError("No symbols available for financial PIT field pack backfill.")
    return FinancialPitFieldPackTask(
        start_date=start_date,
        end_date=end_date,
        start_quarter=_date_to_quarter(start_date),
        end_quarter=_date_to_quarter(end_date),
        symbols=final_symbols,
        fields=fields,
        batch_size=batch_size,
        dry_run=dry_run,
        overwrite=overwrite,
    )


def _date_to_quarter(date: str) -> str:
    ts = pd.Timestamp(date)
    return f"{ts.year}q{((ts.month - 1) // 3) + 1}"
