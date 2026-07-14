from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq
from fastapi import Body, Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from rq_platform.backtest.current_store import CurrentBacktestNotFound, CurrentBacktestStore
from rq_platform.backtest.job_manager import BacktestJobError, BacktestJobManager
from rq_platform.backtest.package_job_manager import StrategyPackageJobManager
from rq_platform.backtest.result_store import BacktestResultStore
from rq_platform.backtest.run_registry import BacktestRunRegistry
from rq_platform.backtest.run_store import BacktestRunResultNotFound, BacktestRunStore
from rq_platform.api.data_routes import router as data_router
from rq_platform.api.factor_routes import router as factor_router
from rq_platform.api.paper_routes import router as paper_router
from rq_platform.api.web_routes import router as web_router
from rq_platform.auth import AuthContext, authenticate_token, legacy_admin_context
from rq_platform.data.data_loader import ResearchDataLoader
from rq_platform.etl.quality_check import check_all_price_datasets
from rq_platform.settings import settings


app = FastAPI(title="quant_platform data api", version="0.1.0")
app.mount(
    "/ui/static",
    StaticFiles(directory=Path(__file__).resolve().parents[1] / "web" / "static"),
    name="ui_static",
)
app.include_router(web_router)
app.include_router(data_router)
app.include_router(paper_router)
app.include_router(factor_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "quant_platform_data_api"}


def require_api_token(
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
    api_token: str | None = Query(default=None),
) -> AuthContext:
    expected_token = settings.api_token
    supplied_token = x_api_token or api_token
    if not supplied_token and (not expected_token or expected_token == "change_me"):
        return legacy_admin_context()
    if not supplied_token:
        raise HTTPException(status_code=401, detail="invalid or missing api token")
    context = authenticate_token(supplied_token)
    if context is None:
        raise HTTPException(status_code=401, detail="invalid or missing api token")
    if not context.enabled:
        raise HTTPException(status_code=403, detail="api token disabled")
    return context


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


@app.get("/backtests")
def backtests(_: None = Depends(require_api_token)) -> dict[str, Any]:
    runs = BacktestResultStore().list_runs()
    return {"count": len(runs), "data": runs}


@app.post("/backtests/run")
def run_backtest(
    request: Request,
    payload: dict[str, Any] = Body(...),
    auth: AuthContext = Depends(require_api_token),
) -> dict[str, Any]:
    strategy_code = payload.get("strategy_code")
    config = payload.get("config")
    try:
        return BacktestJobManager().run_backtest(
            strategy_code=strategy_code,
            config=config,
            submitter=_submitter_metadata(request, auth),
        )
    except BacktestJobError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/backtests/run-package")
def run_backtest_package(
    request: Request,
    file: UploadFile = File(...),
    auth: AuthContext = Depends(require_api_token),
) -> dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="strategy package must be a .zip file")
    upload_dir = settings.backtest_jobs_dir_path / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_path = upload_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{Path(file.filename).name}"
    content = file.file.read()
    max_size = 100 * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail="strategy package exceeds 100MB limit")
    upload_path.write_bytes(content)
    result = StrategyPackageJobManager().run_package(upload_path, submitter=_submitter_metadata(request, auth))
    if result.get("status") == "failed":
        return result
    return result


@app.get("/backtests/current")
def current_backtest(_: None = Depends(require_api_token)) -> dict[str, Any]:
    store = CurrentBacktestStore()
    if not store.current_exists():
        return {"exists": False}
    try:
        summary = store.read_current_json("summary.json")
    except CurrentBacktestNotFound:
        summary = {}
    return {
        "exists": True,
        "run_id": summary.get("run_id"),
        "summary": summary,
    }


@app.get("/backtests/current/summary")
def current_backtest_summary(_: None = Depends(require_api_token)) -> dict[str, Any]:
    return _read_current_json("summary.json")


@app.get("/backtests/current/nav")
def current_backtest_nav(_: None = Depends(require_api_token)) -> dict[str, Any]:
    return _read_current_csv("nav.csv")


@app.get("/backtests/current/trades")
def current_backtest_trades(_: None = Depends(require_api_token)) -> dict[str, Any]:
    return _read_current_csv("trades.csv")


@app.get("/backtests/current/positions")
def current_backtest_positions(_: None = Depends(require_api_token)) -> dict[str, Any]:
    return _read_current_csv("positions.csv")


@app.get("/backtests/current/orders")
def current_backtest_orders(_: None = Depends(require_api_token)) -> dict[str, Any]:
    return _read_current_csv("orders.csv")


@app.get("/backtests/current/logs")
def current_backtest_logs(_: None = Depends(require_api_token)) -> dict[str, str]:
    try:
        return {"logs": CurrentBacktestStore().read_current_text("logs.txt")}
    except (CurrentBacktestNotFound, ValueError) as exc:
        raise HTTPException(status_code=404, detail="current backtest logs not found") from exc


@app.get("/backtests/current/download")
def current_backtest_download(_: None = Depends(require_api_token)) -> FileResponse:
    try:
        zip_path = CurrentBacktestStore().package_current_zip()
    except (CurrentBacktestNotFound, ValueError) as exc:
        raise HTTPException(status_code=404, detail="current backtest result not found") from exc
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=zip_path.name,
    )


@app.delete("/backtests/current")
def delete_current_backtest(_: None = Depends(require_api_token)) -> dict[str, bool]:
    CurrentBacktestStore().delete_current()
    return {"deleted": True}


@app.get("/backtests/runs")
def backtest_runs(
    limit: int = Query(default=50, ge=1, le=500),
    status: str | None = None,
    researcher_id: str | None = None,
    researcher_name: str | None = None,
    include_expired: bool = True,
    _: None = Depends(require_api_token),
) -> list[dict[str, Any]]:
    return BacktestRunRegistry().list_runs(
        limit=limit,
        status=status,
        researcher_id=researcher_id,
        researcher_name=researcher_name,
        include_expired=include_expired,
    )


@app.get("/backtests/runs/{run_id}")
def backtest_run_detail(run_id: str, _: None = Depends(require_api_token)) -> dict[str, Any]:
    record = _get_run_record(run_id)
    return {
        **record,
        "result_urls": _run_result_urls(record["run_id"]),
    }


@app.get("/backtests/runs/{run_id}/summary")
def backtest_run_summary(run_id: str, _: None = Depends(require_api_token)) -> dict[str, Any]:
    return _read_run_json(run_id, "summary.json")


@app.get("/backtests/runs/{run_id}/nav")
def backtest_run_nav(run_id: str, _: None = Depends(require_api_token)) -> dict[str, Any]:
    return _read_run_csv(run_id, "nav.csv")


@app.get("/backtests/runs/{run_id}/trades")
def backtest_run_trades(run_id: str, _: None = Depends(require_api_token)) -> dict[str, Any]:
    return _read_run_csv(run_id, "trades.csv")


@app.get("/backtests/runs/{run_id}/positions")
def backtest_run_positions(run_id: str, _: None = Depends(require_api_token)) -> dict[str, Any]:
    return _read_run_csv(run_id, "positions.csv")


@app.get("/backtests/runs/{run_id}/orders")
def backtest_run_orders(run_id: str, _: None = Depends(require_api_token)) -> dict[str, Any]:
    return _read_run_csv(run_id, "orders.csv")


@app.get("/backtests/runs/{run_id}/logs")
def backtest_run_logs(run_id: str, _: None = Depends(require_api_token)) -> dict[str, str]:
    _get_run_record(run_id)
    try:
        return {"logs": BacktestRunStore().read_text(run_id, "logs.txt")}
    except BacktestRunResultNotFound as exc:
        raise HTTPException(status_code=410, detail="run result files are no longer available") from exc


@app.get("/backtests/runs/{run_id}/download")
def backtest_run_download(run_id: str, _: None = Depends(require_api_token)) -> FileResponse:
    record = _get_run_record(run_id)
    try:
        zip_path = BacktestRunStore().package_zip(run_id)
    except BacktestRunResultNotFound as exc:
        raise HTTPException(status_code=410, detail="run result files are no longer available") from exc
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"backtest_result_{record['run_id']}.zip",
    )


@app.post("/backtests/runs/cleanup")
def cleanup_backtest_runs(_: None = Depends(require_api_token)) -> dict[str, Any]:
    registry = BacktestRunRegistry()
    store = BacktestRunStore()
    expired = registry.cleanup_expired()
    deleted = [run_id for run_id in expired if store.delete_cache(run_id)]
    return {"expired": expired, "deleted": deleted, "count": len(deleted)}


@app.get("/backtests/{run_id}/summary")
def backtest_summary(run_id: str, _: None = Depends(require_api_token)) -> dict[str, Any]:
    return _read_result_json(run_id, "summary.json")


@app.get("/backtests/{run_id}/nav")
def backtest_nav(run_id: str, _: None = Depends(require_api_token)) -> dict[str, Any]:
    return _read_result_csv(run_id, "nav.csv")


@app.get("/backtests/{run_id}/trades")
def backtest_trades(run_id: str, _: None = Depends(require_api_token)) -> dict[str, Any]:
    return _read_result_csv(run_id, "trades.csv")


@app.get("/backtests/{run_id}/positions")
def backtest_positions(run_id: str, _: None = Depends(require_api_token)) -> dict[str, Any]:
    return _read_result_csv(run_id, "positions.csv")


@app.get("/backtests/{run_id}/logs")
def backtest_logs(run_id: str, _: None = Depends(require_api_token)) -> PlainTextResponse:
    try:
        return PlainTextResponse(BacktestResultStore().read_text(run_id, "logs.txt"))
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="backtest logs not found") from exc


@app.get("/backtests/{run_id}/download")
def backtest_download(run_id: str, _: None = Depends(require_api_token)) -> FileResponse:
    store = BacktestResultStore()
    try:
        zip_path = store.package_zip(run_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="backtest result not found") from exc
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=zip_path.name,
    )


def _read_result_json(run_id: str, filename: str) -> dict[str, Any]:
    try:
        return BacktestResultStore().read_json(run_id, filename)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="backtest result not found") from exc


def _read_result_csv(run_id: str, filename: str) -> dict[str, Any]:
    try:
        frame = BacktestResultStore().read_csv(run_id, filename)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="backtest result not found") from exc
    return {"count": int(len(frame)), "data": _records(frame)}


def _read_current_json(filename: str) -> dict[str, Any]:
    try:
        return CurrentBacktestStore().read_current_json(filename)
    except (CurrentBacktestNotFound, ValueError) as exc:
        raise HTTPException(status_code=404, detail="current backtest result not found") from exc


def _read_current_csv(filename: str) -> dict[str, Any]:
    try:
        frame = CurrentBacktestStore().read_current_csv(filename)
    except (CurrentBacktestNotFound, ValueError) as exc:
        raise HTTPException(status_code=404, detail="current backtest result not found") from exc
    return {"count": int(len(frame)), "data": _records(frame)}


def _get_run_record(run_id: str) -> dict[str, Any]:
    record = BacktestRunRegistry().get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="backtest run_id not found")
    return record


def _read_run_json(run_id: str, filename: str) -> dict[str, Any]:
    _get_run_record(run_id)
    try:
        return BacktestRunStore().read_json(run_id, filename)
    except BacktestRunResultNotFound as exc:
        raise HTTPException(status_code=410, detail="run result files are no longer available") from exc


def _read_run_csv(run_id: str, filename: str) -> dict[str, Any]:
    _get_run_record(run_id)
    try:
        frame = BacktestRunStore().read_csv(run_id, filename)
    except BacktestRunResultNotFound as exc:
        raise HTTPException(status_code=410, detail="run result files are no longer available") from exc
    return {"count": int(len(frame)), "data": _records(frame)}


def _run_result_urls(run_id: str) -> dict[str, str]:
    return {
        "summary": f"/backtests/runs/{run_id}/summary",
        "nav": f"/backtests/runs/{run_id}/nav",
        "trades": f"/backtests/runs/{run_id}/trades",
        "positions": f"/backtests/runs/{run_id}/positions",
        "orders": f"/backtests/runs/{run_id}/orders",
        "logs": f"/backtests/runs/{run_id}/logs",
        "download": f"/backtests/runs/{run_id}/download",
        "dashboard": f"/ui/backtests/runs/{run_id}",
    }


def _submitter_metadata(request: Request, auth: AuthContext) -> dict[str, str]:
    client_ip = request.client.host if request.client else ""
    return {
        **auth.to_metadata(),
        "token_type": auth.token_type,
        "client_ip": client_ip,
        "user_agent": request.headers.get("user-agent", ""),
    }


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
