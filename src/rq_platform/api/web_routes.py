from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from rq_platform.web.dashboard_data import (
    format_value,
    load_current_dashboard_data,
    load_data_catalog_dashboard_data,
    load_researcher_usage_dashboard_data,
    load_run_dashboard_data,
    load_runs_dashboard_data,
    table_columns,
)


WEB_ROOT = Path(__file__).resolve().parents[1] / "web"
templates = Jinja2Templates(directory=str(WEB_ROOT / "templates"))
templates.env.filters["fmt"] = format_value

router = APIRouter()


NAV_ITEMS = [
    ("runs", "历史 Runs", "/ui/backtests/runs"),
    ("researchers", "研究员", "/ui/researchers"),
    ("data", "数据", "/ui/data"),
    ("overview", "概览", "/ui/backtests/current/overview"),
    ("nav", "净值曲线", "/ui/backtests/current/nav"),
    ("account", "账户", "/ui/backtests/current/account"),
    ("positions", "持仓", "/ui/backtests/current/positions"),
    ("trades", "交易日志", "/ui/backtests/current/trades"),
    ("orders", "订单", "/ui/backtests/current/orders"),
    ("logs", "日志", "/ui/backtests/current/logs"),
]


@router.get("/ui")
def ui_home() -> RedirectResponse:
    return RedirectResponse(url="/ui/backtests/current", status_code=302)


@router.get("/ui/backtests/current")
def current_dashboard(request: Request):
    return _render(request, "current_overview.html", "overview")


@router.get("/ui/backtests/current/overview")
def current_overview(request: Request):
    return _render(request, "current_overview.html", "overview")


@router.get("/ui/backtests/current/nav")
def current_nav(request: Request):
    return _render(request, "current_nav.html", "nav")


@router.get("/ui/backtests/current/account")
def current_account(request: Request):
    return _render(request, "current_account.html", "account")


@router.get("/ui/backtests/current/positions")
def current_positions(request: Request):
    return _render(request, "current_positions.html", "positions")


@router.get("/ui/backtests/current/trades")
def current_trades(request: Request):
    return _render(request, "current_trades.html", "trades")


@router.get("/ui/backtests/current/orders")
def current_orders(request: Request):
    return _render(request, "current_orders.html", "orders")


@router.get("/ui/backtests/current/logs")
def current_logs(request: Request):
    return _render(request, "current_logs.html", "logs")


@router.get("/ui/backtests/runs")
def run_list(request: Request, researcher_id: str | None = None, researcher_name: str | None = None):
    data = load_runs_dashboard_data(researcher_id=researcher_id, researcher_name=researcher_name)
    return templates.TemplateResponse(
        request,
        "runs.html",
        {
            "request": request,
            "active": "runs",
            "nav_items": NAV_ITEMS,
            "data": data,
            "table_columns": table_columns,
            "page_label": "Backtest Runs",
            "status_label": "registry",
        },
    )


@router.get("/ui/researchers")
def researchers(request: Request):
    data = load_researcher_usage_dashboard_data()
    return templates.TemplateResponse(
        request,
        "researchers.html",
        {
            "request": request,
            "active": "researchers",
            "nav_items": NAV_ITEMS,
            "data": data,
            "table_columns": table_columns,
            "page_label": "Researchers",
            "status_label": "usage",
        },
    )


@router.get("/ui/data")
def data_catalog(request: Request):
    data = load_data_catalog_dashboard_data()
    return templates.TemplateResponse(
        request,
        "data.html",
        {
            "request": request,
            "active": "data",
            "nav_items": NAV_ITEMS,
            "data": data,
            "table_columns": table_columns,
            "page_label": "Researcher Data",
            "status_label": "data ready",
        },
    )


@router.get("/ui/backtests/runs/{run_id}")
def run_detail(request: Request, run_id: str):
    return _render_run(request, run_id, "current_overview.html", "run_overview")


@router.get("/ui/backtests/runs/{run_id}/nav")
def run_nav(request: Request, run_id: str):
    return _render_run(request, run_id, "current_nav.html", "run_nav")


@router.get("/ui/backtests/runs/{run_id}/positions")
def run_positions(request: Request, run_id: str):
    return _render_run(request, run_id, "current_positions.html", "run_positions")


@router.get("/ui/backtests/runs/{run_id}/trades")
def run_trades(request: Request, run_id: str):
    return _render_run(request, run_id, "current_trades.html", "run_trades")


@router.get("/ui/backtests/runs/{run_id}/orders")
def run_orders(request: Request, run_id: str):
    return _render_run(request, run_id, "current_orders.html", "run_orders")


@router.get("/ui/backtests/runs/{run_id}/logs")
def run_logs(request: Request, run_id: str):
    return _render_run(request, run_id, "current_logs.html", "run_logs")


def _render(request: Request, template_name: str, active: str):
    data = load_current_dashboard_data()
    context: dict[str, Any] = {
        "request": request,
        "active": active,
        "nav_items": NAV_ITEMS,
        "data": data,
        "table_columns": table_columns,
    }
    return templates.TemplateResponse(request, template_name, context)


def _render_run(request: Request, run_id: str, template_name: str, active: str):
    data = load_run_dashboard_data(run_id)
    context: dict[str, Any] = {
        "request": request,
        "active": active,
        "nav_items": [
            ("runs", "历史 Runs", "/ui/backtests/runs"),
            ("researchers", "研究员", "/ui/researchers"),
            ("data", "数据", "/ui/data"),
            ("run_overview", "Run 概览", f"/ui/backtests/runs/{run_id}"),
            ("run_nav", "净值曲线", f"/ui/backtests/runs/{run_id}/nav"),
            ("run_positions", "持仓", f"/ui/backtests/runs/{run_id}/positions"),
            ("run_trades", "交易日志", f"/ui/backtests/runs/{run_id}/trades"),
            ("run_orders", "订单", f"/ui/backtests/runs/{run_id}/orders"),
            ("run_logs", "日志", f"/ui/backtests/runs/{run_id}/logs"),
        ],
        "data": data,
        "table_columns": table_columns,
        "page_label": f"Run {run_id}",
        "status_label": "run ready" if data.get("exists") else "run unavailable",
    }
    return templates.TemplateResponse(request, template_name, context)
