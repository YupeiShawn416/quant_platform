from __future__ import annotations

from rq_platform.etl.financial_pit_field_pack_plan import (
    FinancialPitField,
    FinancialPitFieldPackTask,
    build_financial_pit_field_pack_task,
    parse_symbols,
)
from rq_platform.settings import settings


DATASET_NAME = "financial_cashflow_field_pack"
OUTPUT_FILENAME = "financial_cashflow_field_pack.parquet"
STATUS_PATH = settings.data_root_path / "update_logs" / "financial_cashflow_field_pack_status.csv"

CASHFLOW_FIELDS = [
    FinancialPitField("net_operate_cashflow_ttm", "get_pit_financials_ex", "net_operate_cashflowTTM"),
    FinancialPitField("net_invest_cashflow_ttm", "get_pit_financials_ex", "net_invest_cashflowTTM"),
    FinancialPitField("net_finance_cashflow_ttm", "get_pit_financials_ex", "net_finance_cashflowTTM"),
    FinancialPitField("net_cashflow_ttm", "get_pit_financials_ex", "net_cashflowTTM"),
    FinancialPitField("operating_payout_ttm", "get_pit_financials_ex", "operating_payoutTTM"),
    FinancialPitField("sale_service_render_cash_ttm", "get_pit_financials_ex", "sale_service_render_cashTTM"),
    FinancialPitField("cash_flow_from_operating_activities", "get_pit_financials_ex", "cash_flow_from_operating_activities"),
    FinancialPitField("cash_flow_from_investing_activities", "get_pit_financials_ex", "cash_flow_from_investing_activities"),
    FinancialPitField("cash_flow_from_financing_activities", "get_pit_financials_ex", "cash_flow_from_financing_activities"),
    FinancialPitField("cash_from_operating_activities", "get_pit_financials_ex", "cash_from_operating_activities"),
    FinancialPitField("cash_paid_for_operation_activities", "get_pit_financials_ex", "cash_paid_for_operation_activities"),
    FinancialPitField("cash_paid_for_asset", "get_pit_financials_ex", "cash_paid_for_asset"),
    FinancialPitField("cash_received_from_disposal_of_asset", "get_pit_financials_ex", "cash_received_from_disposal_of_asset"),
    FinancialPitField("cash_paid_for_investment_activities", "get_pit_financials_ex", "cash_paid_for_investment_activities"),
    FinancialPitField("cash_received_from_investment_activities", "get_pit_financials_ex", "cash_received_from_investment_activities"),
    FinancialPitField("cash_paid_for_dividend_and_interest", "get_pit_financials_ex", "cash_paid_for_dividend_and_interest"),
    FinancialPitField("cash_paid_for_goods_and_services", "get_pit_financials_ex", "cash_paid_for_goods_and_services"),
    FinancialPitField("cash_paid_for_employee", "get_pit_financials_ex", "cash_paid_for_employee"),
    FinancialPitField("cash_paid_for_taxes", "get_pit_financials_ex", "cash_paid_for_taxes"),
    FinancialPitField("net_inc_cash_and_equivalents", "get_pit_financials_ex", "net_inc_cash_and_equivalents"),
    FinancialPitField("cash_equivalent_increase", "get_pit_financials_ex", "cash_equivalent_increase"),
    FinancialPitField("begin_period_cash_equivalent", "get_pit_financials_ex", "begin_period_cash_equivalent"),
    FinancialPitField("end_period_cash_equivalent", "get_pit_financials_ex", "end_period_cash_equivalent"),
    FinancialPitField("cash_equivalent", "get_pit_financials_ex", "cash_equivalent"),
]


def select_cashflow_fields(fields: list[str] | None = None) -> list[FinancialPitField]:
    if not fields:
        return CASHFLOW_FIELDS.copy()
    requested = set(fields)
    selected = [field for field in CASHFLOW_FIELDS if field.canonical_field in requested]
    missing = sorted(requested - {field.canonical_field for field in selected})
    if missing:
        raise ValueError(f"Unknown cash-flow fields: {', '.join(missing)}")
    return selected


def build_financial_cashflow_field_pack_task(
    *,
    start_date: str,
    end_date: str,
    symbols: list[str] | None,
    fields: list[FinancialPitField],
    batch_size: int,
    dry_run: bool,
    overwrite: bool,
) -> FinancialPitFieldPackTask:
    return build_financial_pit_field_pack_task(
        start_date=start_date,
        end_date=end_date,
        symbols=symbols,
        fields=fields,
        batch_size=batch_size,
        dry_run=dry_run,
        overwrite=overwrite,
    )


__all__ = [
    "CASHFLOW_FIELDS",
    "DATASET_NAME",
    "OUTPUT_FILENAME",
    "STATUS_PATH",
    "build_financial_cashflow_field_pack_task",
    "parse_symbols",
    "select_cashflow_fields",
]
