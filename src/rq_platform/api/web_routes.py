from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from rq_platform.web.dashboard_data import (
    format_value,
    load_current_dashboard_data,
    table_columns,
)


WEB_ROOT = Path(__file__).resolve().parents[1] / "web"
templates = Jinja2Templates(directory=str(WEB_ROOT / "templates"))
templates.env.filters["fmt"] = format_value

router = APIRouter()


NAV_ITEMS = [
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
