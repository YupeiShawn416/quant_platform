from __future__ import annotations

import math
from numbers import Real
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import Response

from rq_platform.auth import AuthContext, authenticate_token, legacy_admin_context
from rq_platform.data.data_access_log import append_data_access_log
from rq_platform.data.query_service import (
    DEFAULT_QUERY_LIMIT,
    MAX_QUERY_LIMIT,
    DataQueryError,
    DataQueryService,
    DatasetNotFoundError,
    get_dataset_spec,
    parse_csv_list,
)
from rq_platform.settings import settings


router = APIRouter(prefix="/data", tags=["data"])


def require_data_api_token(
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


@router.get("/datasets")
def list_datasets(_: AuthContext = Depends(require_data_api_token)) -> dict[str, Any]:
    datasets = DataQueryService().list_datasets()
    return {"count": len(datasets), "datasets": datasets}


@router.get("/coverage")
def data_coverage(_: AuthContext = Depends(require_data_api_token)) -> dict[str, Any]:
    return DataQueryService().coverage()


@router.get("/schema/{dataset}")
def data_schema(dataset: str, _: AuthContext = Depends(require_data_api_token)) -> dict[str, Any]:
    try:
        fields = DataQueryService().schema(dataset)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"dataset": dataset, "fields": fields}


@router.get("/query/{dataset}", response_model=None)
def query_dataset(
    dataset: str,
    request: Request,
    start_date: str | None = None,
    end_date: str | None = None,
    dates: str | None = None,
    trade_date: str | None = None,
    order_book_id: str | None = None,
    fields: str | None = None,
    limit: str = Query(default=str(DEFAULT_QUERY_LIMIT)),
    offset: str = Query(default="0"),
    format: str = Query(default="json"),
    auth: AuthContext = Depends(require_data_api_token),
):
    limit_value = _parse_query_int("limit", limit, minimum=1, maximum=MAX_QUERY_LIMIT)
    offset_value = _parse_query_int("offset", offset, minimum=0)
    if format not in {"json", "csv"}:
        raise _data_api_error(400, "invalid_parameter", "format must be json or csv")
    field_list = parse_csv_list(fields)
    order_book_ids = parse_csv_list(order_book_id)
    date_values = parse_csv_list(dates or trade_date)
    try:
        spec = get_dataset_spec(dataset)
    except DatasetNotFoundError as exc:
        raise _data_api_error(404, "dataset_not_found", str(exc)) from exc
    try:
        frame, has_more = DataQueryService().query(
            dataset,
            start_date=start_date,
            end_date=end_date,
            date_values=date_values,
            order_book_ids=order_book_ids,
            fields=field_list,
            limit=limit_value,
            offset=offset_value,
        )
    except DatasetNotFoundError as exc:
        raise _data_api_error(404, "dataset_not_found", str(exc)) from exc
    except DataQueryError as exc:
        raise _data_api_error(400, "invalid_query", str(exc)) from exc

    _log_query(request, auth, dataset, start_date, end_date, date_values, order_book_ids, field_list, limit_value, offset_value, len(frame))

    if format == "csv":
        csv_text = frame.to_csv(index=False)
        return Response(
            csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{dataset}.csv"'},
        )
    return {
        "dataset": dataset,
        "start_date": start_date,
        "end_date": end_date,
        "date_column": spec.date_column,
        "limit": limit_value,
        "offset": offset_value,
        "row_count": int(len(frame)),
        "has_more": bool(has_more),
        "records": _records(frame),
    }


def _parse_query_int(field_name: str, value: str, *, minimum: int, maximum: int | None = None) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise _data_api_error(400, "invalid_parameter", f"{field_name} must be an integer") from exc
    if parsed < minimum:
        raise _data_api_error(400, "invalid_parameter", f"{field_name} must be >= {minimum}")
    if maximum is not None and parsed > maximum:
        raise _data_api_error(400, "invalid_parameter", f"{field_name} must be <= {maximum}")
    return parsed


def _data_api_error(status_code: int, error_code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error_code": error_code, "message": message})


def _log_query(
    request: Request,
    auth: AuthContext,
    dataset: str,
    start_date: str | None,
    end_date: str | None,
    date_values: list[str] | None,
    order_book_ids: list[str] | None,
    fields: list[str] | None,
    limit: int,
    offset: int,
    returned_rows: int,
) -> None:
    append_data_access_log(
        {
            "researcher_id": auth.researcher_id,
            "researcher_name": auth.researcher_name,
            "dataset": dataset,
            "start_date": start_date,
            "end_date": end_date,
            "dates": date_values or [],
            "order_book_id_count": len(order_book_ids or []),
            "fields": fields or [],
            "limit": limit,
            "offset": offset,
            "returned_rows": returned_rows,
            "client_ip": request.client.host if request.client else "",
            "user_agent": request.headers.get("user-agent", ""),
        }
    )


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    clean = frame.astype(object).where(pd.notna(frame), None)
    return [{key: _json_safe_value(value) for key, value in row.items()} for row in clean.to_dict(orient="records")]


def _json_safe_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Real) and not math.isfinite(float(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value
