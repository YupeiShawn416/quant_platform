from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq
from fastapi import Depends, FastAPI, Header, HTTPException, Query

from rq_platform.data.data_loader import ResearchDataLoader
from rq_platform.etl.quality_check import check_all_price_datasets
from rq_platform.settings import settings


app = FastAPI(title="quant_platform data api", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "quant_platform_data_api"}


def require_api_token(
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
    api_token: str | None = Query(default=None),
) -> None:
    expected_token = settings.api_token
    if not expected_token or expected_token == "change_me":
        return
    supplied_token = x_api_token or api_token
    if supplied_token != expected_token:
        raise HTTPException(status_code=401, detail="invalid or missing api token")


@app.get("/status")
def status(_: None = Depends(require_api_token)) -> dict[str, Any]:
    data_root = settings.data_root_path
    datasets = {
        "instruments": data_root / "instruments" / "instruments.parquet",
        "trading_calendar": data_root
        / "trading_calendar"
        / "trading_calendar.parquet",
        "prices_1d_pre_2025": data_root / "prices_1d_pre" / "year=2025.parquet",
        "prices_1d_none_2025": data_root / "prices_1d_none" / "year=2025.parquet",
    }
    return {
        "data_root": str(data_root),
        "datasets": {
            name: _dataset_status(path) for name, path in datasets.items()
        },
    }


@app.get("/instruments")
def instruments(
    limit: int = Query(default=20, ge=1, le=500),
    _: None = Depends(require_api_token),
) -> dict[str, Any]:
    path = settings.data_root_path / "instruments" / "instruments.parquet"
    frame = _read_required_parquet(path, "本地 instruments.parquet 不存在")
    frame = frame.head(limit)
    return {"count": int(len(frame)), "data": _records(frame)}


@app.get("/calendar")
def calendar(
    start: str | None = None,
    end: str | None = None,
    _: None = Depends(require_api_token),
) -> dict[str, Any]:
    path = settings.data_root_path / "trading_calendar" / "trading_calendar.parquet"
    frame = _read_required_parquet(path, "本地 trading_calendar.parquet 不存在")
    if "trade_date" not in frame.columns:
        raise HTTPException(status_code=500, detail="trading_calendar 缺少 trade_date 字段")
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
    if start is not None:
        _parse_date(start, "start")
        frame = frame[frame["trade_date"] >= start]
    if end is not None:
        _parse_date(end, "end")
        frame = frame[frame["trade_date"] <= end]
    return {"count": int(len(frame)), "data": _records(frame)}


@app.get("/prices")
def prices(
    symbols: str,
    start: str,
    end: str,
    adjust_type: str = "pre",
    fields: str | None = None,
    _: None = Depends(require_api_token),
) -> dict[str, Any]:
    if adjust_type not in {"pre", "none"}:
        raise HTTPException(status_code=400, detail="adjust_type 只允许 pre 或 none")

    start_date = _parse_date(start, "start")
    end_date = _parse_date(end, "end")
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start 不能晚于 end")
    if (end_date - start_date).days > 366:
        raise HTTPException(status_code=400, detail="日期跨度不能超过 366 天")

    symbol_list = [item.strip() for item in symbols.split(",") if item.strip()]
    if not symbol_list:
        raise HTTPException(status_code=400, detail="symbols 不能为空")
    if len(symbol_list) > 200:
        raise HTTPException(status_code=400, detail="symbols 最多允许 200 个")

    field_list = None
    if fields:
        field_list = [item.strip() for item in fields.split(",") if item.strip()]

    try:
        frame = ResearchDataLoader().load_prices(
            symbols=symbol_list,
            start=start,
            end=end,
            adjust_type=adjust_type,
            fields=field_list,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"本地行情查询失败: {type(exc).__name__}") from exc

    return {
        "count": int(len(frame)),
        "symbols": symbol_list,
        "adjust_type": adjust_type,
        "start": start,
        "end": end,
        "data": _records(frame),
    }


@app.get("/data-quality")
def data_quality(
    year: int = 2025, _: None = Depends(require_api_token)
) -> dict[str, Any]:
    return {"year": year, "results": check_all_price_datasets(year=year)}


def _dataset_status(path: Path) -> dict[str, Any]:
    exists = path.exists()
    return {
        "exists": exists,
        "path": str(path),
        "rows": _parquet_rows(path) if exists else 0,
    }


def _parquet_rows(path: Path) -> int:
    try:
        return int(pq.ParquetFile(path).metadata.num_rows)
    except Exception:
        return int(len(pd.read_parquet(path)))


def _read_required_parquet(path: Path, message: str) -> pd.DataFrame:
    if not path.exists():
        raise HTTPException(status_code=404, detail=message)
    try:
        return pd.read_parquet(path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"读取本地 Parquet 失败: {type(exc).__name__}") from exc


def _parse_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} 必须是 YYYY-MM-DD 日期格式",
        ) from exc


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    clean = frame.where(pd.notna(frame), None)
    return clean.to_dict(orient="records")
