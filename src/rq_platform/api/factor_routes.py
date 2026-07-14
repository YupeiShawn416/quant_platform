from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from rq_platform.auth import AuthContext, authenticate_token, legacy_admin_context
from rq_platform.factors.factor_reports import public_artifact_path, records
from rq_platform.factors.factor_registry import FactorRegistry
from rq_platform.factors.factor_store import FactorFileNotFound, FactorStore
from rq_platform.factors.factor_weights import FactorWeightGenerator
from rq_platform.settings import settings


router = APIRouter(prefix="/factors", tags=["factors"])


def require_factor_api_token(
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


@router.get("")
def list_factors(
    category: str | None = None,
    universe: str | None = None,
    keyword: str | None = None,
    _: AuthContext = Depends(require_factor_api_token),
) -> dict[str, Any]:
    store = FactorStore()
    rows = []
    for item in FactorRegistry().list_factors(category=category, keyword=keyword):
        try:
            summary = store.read_analysis_json(item["factor_id"])
        except FactorFileNotFound:
            summary = {}
        row = {**item, "summary": summary}
        if universe and item.get("default_universe") != universe:
            continue
        rows.append(row)
    return {"count": len(rows), "data": rows}


@router.get("/{factor_id}")
def factor_detail(factor_id: str, _: AuthContext = Depends(require_factor_api_token)) -> dict[str, Any]:
    try:
        meta = FactorRegistry().get(factor_id).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        summary = FactorStore().read_analysis_json(factor_id)
    except FactorFileNotFound:
        summary = {}
    return {"metadata": meta, "summary": summary}


@router.get("/{factor_id}/ic")
def factor_ic(factor_id: str, _: AuthContext = Depends(require_factor_api_token)) -> dict[str, Any]:
    return _analysis_csv(factor_id, "ic_daily.csv")


@router.get("/{factor_id}/groups")
def factor_groups(factor_id: str, _: AuthContext = Depends(require_factor_api_token)) -> dict[str, Any]:
    return _analysis_csv(factor_id, "group_returns.csv")


@router.get("/{factor_id}/nav")
def factor_nav(factor_id: str, _: AuthContext = Depends(require_factor_api_token)) -> dict[str, Any]:
    return _analysis_csv(factor_id, "group_nav.csv")


@router.get("/{factor_id}/turnover")
def factor_turnover(factor_id: str, _: AuthContext = Depends(require_factor_api_token)) -> dict[str, Any]:
    return _analysis_csv(factor_id, "turnover.csv")


@router.get("/{factor_id}/top-bottom")
def factor_top_bottom(factor_id: str, _: AuthContext = Depends(require_factor_api_token)) -> dict[str, Any]:
    return _analysis_csv(factor_id, "top_bottom_latest.csv")


@router.post("/{factor_id}/generate-weights")
def factor_generate_weights(
    factor_id: str,
    payload: dict[str, Any],
    _: AuthContext = Depends(require_factor_api_token),
) -> dict[str, Any]:
    try:
        result = FactorWeightGenerator().generate(
            factor_id=factor_id,
            start_date=payload.get("start_date"),
            end_date=payload.get("end_date"),
            top_quantile=float(payload.get("top_quantile", 0.2)),
            max_names=int(payload.get("max_names", 50)),
            rebalance_frequency=payload.get("rebalance_frequency", "daily"),
            weight_method=payload.get("weight_method", "equal"),
            min_coverage_threshold=float(payload.get("min_coverage_threshold", 0.5)),
            use_latest_usable_date=bool(payload.get("use_latest_usable_date", False)),
        )
    except (FactorFileNotFound, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        **result,
        "output_dir": public_artifact_path(result["output_dir"]),
        "target_weights": public_artifact_path(result["target_weights"]),
        "manifest": public_artifact_path(result["manifest"]),
    }


def _analysis_csv(factor_id: str, filename: str) -> dict[str, Any]:
    try:
        frame = FactorStore().read_analysis_csv(factor_id, filename)
    except FactorFileNotFound as exc:
        raise HTTPException(status_code=404, detail=f"{filename} not found; run factor analysis first") from exc
    return {"count": int(len(frame)), "data": records(frame)}
