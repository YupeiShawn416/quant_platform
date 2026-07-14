from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse

from rq_platform.auth import AuthContext, authenticate_token, legacy_admin_context
from rq_platform.paper.paper_account import PaperAccount, sanitize_paper_id
from rq_platform.paper.paper_engine import PaperEngine, PaperEngineError
from rq_platform.paper.paper_registry import PaperAccountRegistry
from rq_platform.paper.paper_store import PaperAccountNotFound, PaperAccountStore
from rq_platform.paper.paper_validator import PaperValidationError, validate_target_weights
from rq_platform.settings import settings


router = APIRouter(prefix="/paper", tags=["paper"])


def require_paper_api_token(
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


@router.get("/accounts")
def list_paper_accounts(
    researcher_id: str | None = None,
    status: str | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    _: AuthContext = Depends(require_paper_api_token),
) -> dict[str, Any]:
    rows = PaperAccountRegistry().list_accounts(researcher_id=researcher_id, status=status, limit=limit)
    return {"count": len(rows), "data": rows}


@router.post("/accounts")
def create_paper_account(
    payload: dict[str, Any],
    request: Request,
    auth: AuthContext = Depends(require_paper_api_token),
) -> dict[str, Any]:
    strategy_name = str(payload.get("strategy_name") or "").strip()
    if not strategy_name:
        raise HTTPException(status_code=400, detail="strategy_name is required")
    initial_cash = float(payload.get("initial_cash") or 0)
    if initial_cash <= 0:
        raise HTTPException(status_code=400, detail="initial_cash must be > 0")
    paper_id = sanitize_paper_id(payload.get("paper_id") or strategy_name)
    account = PaperAccount(
        paper_id=paper_id,
        strategy_name=strategy_name,
        researcher_id=auth.researcher_id,
        researcher_name=auth.researcher_name,
        initial_cash=initial_cash,
        benchmark=payload.get("benchmark"),
    )
    try:
        PaperAccountStore().create_account(account)
    except FileExistsError as exc:
        raise HTTPException(status_code=400, detail=f"paper account already exists: {account.paper_id}") from exc
    PaperAccountRegistry().upsert(account)
    PaperAccountStore().append_log(
        account.paper_id,
        {
            "event": "create_account",
            "researcher_id": auth.researcher_id,
            "researcher_name": auth.researcher_name,
            "client_ip": request.client.host if request.client else "",
            "user_agent": request.headers.get("user-agent", ""),
        },
    )
    return {"status": "success", "account": account.to_dict()}


@router.get("/accounts/{paper_id}")
def get_paper_account(paper_id: str, _: AuthContext = Depends(require_paper_api_token)) -> dict[str, Any]:
    try:
        account = PaperAccountStore().read_account(paper_id)
    except PaperAccountNotFound as exc:
        raise HTTPException(status_code=404, detail="paper account not found") from exc
    return {"exists": True, "account": account.to_dict()}


@router.post("/accounts/{paper_id}/target-weights")
def upload_target_weights(
    paper_id: str,
    file: UploadFile = File(...),
    _: AuthContext = Depends(require_paper_api_token),
) -> dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="target weights must be a csv file")
    content = file.file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="target weights csv exceeds 5MB limit")
    try:
        frame = pd.read_csv(BytesIO(content))
        validated = validate_target_weights(frame)
        PaperAccountStore().save_target_weights(paper_id, validated)
        PaperAccountStore().append_log(
            paper_id,
            {"event": "upload_target_weights", "rows": int(len(validated)), "filename": file.filename},
        )
    except PaperAccountNotFound as exc:
        raise HTTPException(status_code=404, detail="paper account not found") from exc
    except (PaperValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "success", "paper_id": sanitize_paper_id(paper_id), "rows": int(len(validated))}


@router.post("/accounts/{paper_id}/run-daily")
def run_paper_daily(
    paper_id: str,
    payload: dict[str, Any],
    _: AuthContext = Depends(require_paper_api_token),
) -> dict[str, Any]:
    trade_date = str(payload.get("trade_date") or "").strip()
    if not trade_date:
        raise HTTPException(status_code=400, detail="trade_date is required")
    try:
        return PaperEngine().run_daily(paper_id, trade_date)
    except PaperAccountNotFound as exc:
        raise HTTPException(status_code=404, detail="paper account not found") from exc
    except (PaperEngineError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/run-daily-all")
def run_paper_daily_all(
    payload: dict[str, Any],
    _: AuthContext = Depends(require_paper_api_token),
) -> dict[str, Any]:
    trade_date = str(payload.get("trade_date") or "").strip()
    if not trade_date:
        raise HTTPException(status_code=400, detail="trade_date is required")
    results: list[dict[str, Any]] = []
    for account in PaperAccountRegistry().list_accounts(status="active", limit=10000):
        try:
            results.append(PaperEngine().run_daily(account["paper_id"], trade_date))
        except Exception as exc:
            results.append(
                {
                    "status": "failed",
                    "paper_id": account.get("paper_id"),
                    "trade_date": trade_date,
                    "error": str(exc),
                }
            )
    return {"trade_date": trade_date, "count": len(results), "results": results}


@router.get("/accounts/{paper_id}/nav")
def paper_nav(paper_id: str, _: AuthContext = Depends(require_paper_api_token)) -> dict[str, Any]:
    return _read_csv(paper_id, "nav.csv")


@router.get("/accounts/{paper_id}/positions")
def paper_positions(paper_id: str, _: AuthContext = Depends(require_paper_api_token)) -> dict[str, Any]:
    return _read_csv(paper_id, "positions.csv")


@router.get("/accounts/{paper_id}/trades")
def paper_trades(paper_id: str, _: AuthContext = Depends(require_paper_api_token)) -> dict[str, Any]:
    return _read_csv(paper_id, "trades.csv")


@router.get("/accounts/{paper_id}/orders")
def paper_orders(paper_id: str, _: AuthContext = Depends(require_paper_api_token)) -> dict[str, Any]:
    return _read_csv(paper_id, "orders.csv")


@router.get("/accounts/{paper_id}/logs")
def paper_logs(paper_id: str, _: AuthContext = Depends(require_paper_api_token)) -> dict[str, Any]:
    try:
        logs = PaperAccountStore().read_logs(paper_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"count": len(logs), "logs": logs}


@router.get("/accounts/{paper_id}/download")
def paper_download(paper_id: str, _: AuthContext = Depends(require_paper_api_token)) -> FileResponse:
    try:
        zip_path = PaperAccountStore().package_zip(paper_id)
    except PaperAccountNotFound as exc:
        raise HTTPException(status_code=404, detail="paper account not found") from exc
    return FileResponse(zip_path, media_type="application/zip", filename=zip_path.name)


def _read_csv(paper_id: str, filename: str) -> dict[str, Any]:
    try:
        frame = PaperAccountStore().read_csv(paper_id, filename)
    except PaperAccountNotFound as exc:
        raise HTTPException(status_code=404, detail="paper account file not found") from exc
    clean = frame.where(pd.notna(frame), None)
    return {"count": int(len(clean)), "data": clean.to_dict(orient="records")}
