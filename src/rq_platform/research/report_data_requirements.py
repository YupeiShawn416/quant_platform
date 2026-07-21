from __future__ import annotations

from dataclasses import dataclass
from typing import Any


FIELD_TYPES = {"raw", "derived", "label", "event", "metadata"}
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


@dataclass(frozen=True)
class FieldRequirement:
    priority: str
    data_pack: str
    canonical_field: str
    chinese_name: str
    field_type: str
    required_frequency: str
    recommended_storage_frequency: str
    source_report: str
    factor_usage: str
    derivation_formula: str = ""
    required_raw_fields: tuple[str, ...] = ()
    rqdata_candidate_function: str = ""
    rqdata_candidate_field: str = ""
    recommended_dataset_name: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data["required_raw_fields"] = ",".join(self.required_raw_fields)
        return data


def load_research_report_requirements() -> list[FieldRequirement]:
    rows: list[FieldRequirement] = []
    rows.extend(_daily_market_core())
    rows.extend(_valuation_core())
    rows.extend(_financial_pit_core())
    rows.extend(_corporate_actions())
    rows.extend(_index_and_industry())
    rows.extend(_monthly_derived())
    rows.extend(_capital_flow())
    rows.extend(_shareholder_analyst_events())
    rows.extend(_topic_fields())
    rows.extend(_deferred_fields())
    return sorted(rows, key=lambda item: (PRIORITY_ORDER[item.priority], item.data_pack, item.field_type, item.canonical_field))


def raw_probe_requirements(requirements: list[FieldRequirement] | None = None) -> list[FieldRequirement]:
    requirements = requirements or load_research_report_requirements()
    return [item for item in requirements if item.field_type in {"raw", "label", "event", "metadata"} and item.priority != "P3"]


def derived_requirements(requirements: list[FieldRequirement] | None = None) -> list[FieldRequirement]:
    requirements = requirements or load_research_report_requirements()
    return [item for item in requirements if item.field_type == "derived"]


def _req(priority, pack, field, cn, ftype, freq, storage, usage, formula="", raw=(), fn="", rq_field="", ds="", notes=""):
    return FieldRequirement(priority, pack, field, cn, ftype, freq, storage, "research_report_requirements", usage, formula, tuple(raw), fn, rq_field, ds, notes)


def _daily_market_core():
    raw = [
        ("open", "开盘价"),
        ("high", "最高价"),
        ("low", "最低价"),
        ("close", "收盘价"),
        ("prev_close", "前收盘价"),
        ("volume", "成交量"),
        ("total_turnover", "成交额"),
        ("vwap", "成交均价"),
        ("adjust_factor", "复权因子"),
        ("limit_up", "涨停价"),
        ("limit_down", "跌停价"),
    ]
    labels = [
        ("is_limit_up", "是否涨停"),
        ("is_limit_down", "是否跌停"),
        ("is_suspended", "是否停牌"),
        ("is_st", "是否ST"),
        ("is_listed", "是否上市"),
        ("is_tradable", "是否可交易"),
        ("board_type", "板块"),
        ("exchange", "交易所"),
    ]
    derived = [
        ("return_1d", "日收益", "close / prev_close - 1", ("close", "prev_close")),
        ("overnight_return", "隔夜收益", "open / prev_close - 1", ("open", "prev_close")),
        ("intraday_return", "日内收益", "close / open - 1", ("close", "open")),
        ("max_return_20d", "20日最大收益", "rolling max(return_1d, 20)", ("return_1d",)),
        ("amihud", "Amihud非流动性", "abs(return_1d) / total_turnover", ("return_1d", "total_turnover")),
        ("volatility", "波动率", "rolling std(return_1d)", ("return_1d",)),
        ("momentum", "动量", "rolling cumulative return", ("return_1d",)),
        ("reversal", "反转", "lagged short horizon return", ("return_1d",)),
    ]
    out = [_req("P0", "daily_market_core", f, cn, "raw", "daily", "daily", "daily price and liquidity", fn="get_price", rq_field=f, ds="prices_1d_none") for f, cn in raw]
    out.extend(_req("P0", "daily_market_core", f, cn, "label", "daily/static", "daily/static", "tradability and universe filters", ds="tradability_1d/instruments") for f, cn in labels)
    out.extend(_req("P0", "daily_market_core", f, cn, "derived", "daily", "derived daily/monthly", "market factors", formula, raw_fields, ds="derived") for f, cn, formula, raw_fields in derived)
    return out


def _valuation_core():
    fields = [
        ("market_cap", "总市值"),
        ("float_market_cap", "流通市值"),
        ("circulating_market_cap", "流通市值"),
        ("total_share", "总股本"),
        ("circulating_share", "流通股本"),
        ("free_float_share", "自由流通股本"),
        ("turnover_rate", "换手率"),
        ("pb", "市净率"),
        ("pe", "市盈率"),
        ("pe_ttm", "滚动市盈率"),
        ("ps", "市销率"),
        ("ps_ttm", "滚动市销率"),
        ("pcf", "市现率"),
        ("pcf_ttm", "滚动市现率"),
    ]
    return [_req("P0", "valuation_core", f, cn, "raw", "daily/month_end", "daily + month_end snapshot", "value, size, liquidity", fn="get_factor", rq_field=f, ds="valuation_1d") for f, cn in fields]


def _financial_pit_core():
    fields = [
        ("revenue", "营业收入"),
        ("operating_cost", "营业成本"),
        ("operating_profit", "营业利润"),
        ("net_profit", "净利润"),
        ("net_profit_parent", "归母净利润"),
        ("deduct_net_profit_parent", "扣非归母净利润"),
        ("ebit", "EBIT"),
        ("interest_expense", "利息费用"),
        ("sales_expense", "销售费用"),
        ("admin_expense", "管理费用"),
        ("financial_expense", "财务费用"),
        ("rd_expense", "研发费用"),
        ("total_assets", "总资产"),
        ("total_liabilities", "总负债"),
        ("current_assets", "流动资产"),
        ("current_liabilities", "流动负债"),
        ("cash_and_equivalents", "货币资金"),
        ("equity_parent", "归母股东权益"),
        ("total_equity", "股东权益"),
        ("inventory", "存货"),
        ("accounts_receivable", "应收账款"),
        ("intangible_assets", "无形资产"),
        ("goodwill", "商誉"),
        ("contract_liabilities", "合同负债"),
        ("advance_receipts", "预收账款"),
        ("fixed_assets", "固定资产"),
        ("net_operate_cash_flow", "经营现金流净额"),
        ("net_invest_cash_flow", "投资现金流净额"),
        ("net_finance_cash_flow", "融资现金流净额"),
        ("capex", "资本开支"),
        ("depreciation_amortization", "折旧摊销"),
        ("dividends_paid", "支付股利"),
        ("cash_paid_dividend_interest", "支付股利利息现金"),
    ]
    derived = [
        ("roe", "ROE", "single_quarter_parent_profit / lagged equity_parent", ("net_profit_parent", "equity_parent")),
        ("roic", "ROIC", "NOPAT / invested capital", ("operating_profit", "total_assets", "cash_and_equivalents")),
        ("gross_margin", "毛利率", "(revenue - operating_cost) / revenue", ("revenue", "operating_cost")),
        ("operating_margin", "营业利润率", "operating_profit / revenue", ("operating_profit", "revenue")),
        ("asset_turnover", "资产周转率", "revenue / average total_assets", ("revenue", "total_assets")),
        ("debt_to_asset", "资产负债率", "total_liabilities / total_assets", ("total_liabilities", "total_assets")),
        ("fcf", "自由现金流", "net_operate_cash_flow - capex", ("net_operate_cash_flow", "capex")),
        ("ev", "企业价值", "market_cap + total_liabilities - cash_and_equivalents", ("market_cap", "total_liabilities", "cash_and_equivalents")),
        ("fcfy", "自由现金流收益率", "fcf_ttm / ev", ("fcf", "ev")),
        ("rd_to_market_cap", "研发市值比", "rd_expense_ttm / market_cap", ("rd_expense", "market_cap")),
        ("rd_to_revenue", "研发收入比", "rd_expense_ttm / revenue_ttm", ("rd_expense", "revenue")),
        ("rd_growth_yoy", "研发同比增长", "rd_expense_ttm / lag(rd_expense_ttm, 12m) - 1", ("rd_expense",)),
    ]
    out = [_req("P0", "financial_pit_core", f, cn, "raw", "quarterly PIT", "quarterly PIT", "quality, value, R&D, FCF", fn="get_pit_financials_ex", rq_field=f, ds="financial_pit_quarterly") for f, cn in fields]
    out.extend(_req("P0", "financial_pit_core", f, cn, "derived", "quarterly/monthly", "derived monthly", "financial factors", formula, raw_fields, ds="derived financial panel") for f, cn, formula, raw_fields in derived)
    return out


def _corporate_actions():
    fields = [
        ("cash_dividend_per_share", "每股现金分红"),
        ("cash_dividend_total", "现金分红总额"),
        ("dividend_announcement_date", "分红公告日"),
        ("ex_dividend_date", "除息日"),
        ("record_date", "股权登记日"),
        ("payment_date", "派息日"),
        ("total_share", "总股本"),
        ("circulating_share", "流通股本"),
        ("free_float_share", "自由流通股本"),
        ("restricted_share", "限售股本"),
        ("share_change_date", "股本变动日"),
        ("split_ratio", "拆股比例"),
        ("bonus_share_ratio", "送股比例"),
        ("transfer_share_ratio", "转增比例"),
        ("rights_issue_ratio", "配股比例"),
        ("rights_issue_price", "配股价格"),
        ("adjust_factor", "复权因子"),
    ]
    derived = [
        ("dividend_ttm", "TTM分红", "rolling sum cash_dividend", ("cash_dividend_total",)),
        ("dividend_yield_ttm", "股息率", "dividend_ttm / market_cap", ("dividend_ttm", "market_cap")),
        ("split_adjusted_return", "除权调整收益", "price return adjusted by corporate actions", ("adjust_factor", "close")),
        ("turnover_float_adjusted", "流通股调整换手", "volume / free_float_share", ("volume", "free_float_share")),
    ]
    out = [_req("P0", "corporate_actions_dividend_share_capital", f, cn, "event" if "date" in f or "dividend" in f or "ratio" in f else "raw", "event/month_end", "event + month_end snapshot", "dividend, share capital, adjustment", fn="corporate_action", rq_field=f, ds="corporate_actions") for f, cn in fields]
    out.extend(_req("P0", "corporate_actions_dividend_share_capital", f, cn, "derived", "monthly", "derived monthly", "dividend and adjustment factors", formula, raw_fields, ds="derived") for f, cn, formula, raw_fields in derived)
    return out


def _index_and_industry():
    indexes = ["000985.XSHG", "000300.XSHG", "000905.XSHG", "000906.XSHG", "000852.XSHG", "000955.XSHG", "000932.XSHG", "000931.XSHG", "tech_chinext_star"]
    industry = ["sw_l1", "sw_l2", "sw_l3", "citics_l1", "citics_l2", "citics_l3", "csi_l1", "csi_l2", "financial_label", "real_estate_label", "technology_label", "consumer_label", "utilities_label", "bank_label", "broker_label"]
    out = [_req("P0", "index_universe_extended", f"index_members_{idx}", idx, "label", "daily/month_end", "daily/month_end", "index universe", fn="index_components", rq_field=idx, ds="index_components/index_weights") for idx in indexes]
    out.extend(_req("P0", "industry_taxonomy", f, f, "label", "low frequency/daily", "version table or daily mapping", "industry neutralization", fn="industry", rq_field=f, ds="industry_classification") for f in industry)
    return out


def _monthly_derived():
    fields = [
        ("month_end", "月末", "last trading day of month", ("trading_calendar",)),
        ("monthly_return", "月收益", "product(1 + return_1d) - 1 or adjusted close ratio", ("prices_1d_pre.close",)),
        ("monthly_forward_return", "下月收益", "lead(monthly_return, 1)", ("monthly_return",)),
        ("adjusted_month_end_close", "复权月末价", "month-end prices_1d_pre.close", ("prices_1d_pre.close",)),
        ("market_cap_month_end", "月末总市值", "month-end market_cap", ("market_cap",)),
        ("float_market_cap_month_end", "月末流通市值", "month-end float_market_cap", ("float_market_cap",)),
        ("turnover_monthly_mean", "月均换手", "mean(turnover_rate)", ("turnover_rate",)),
        ("turnover_monthly_sum", "月总换手", "sum(turnover_rate)", ("turnover_rate",)),
        ("amount_monthly_mean", "月均成交额", "mean(total_turnover)", ("total_turnover",)),
        ("amihud_monthly", "月Amihud", "mean(abs(return_1d) / total_turnover)", ("return_1d", "total_turnover")),
        ("amihud_ex_limit_monthly", "剔除涨跌停Amihud", "amihud excluding limit days", ("return_1d", "total_turnover", "limit_up", "limit_down")),
        ("beta_12m", "12月beta", "rolling regression stock return on market", ("monthly_return", "market_return")),
        ("beta_36m", "36月beta", "rolling regression stock return on market", ("monthly_return", "market_return")),
        ("beta_60m", "60月beta", "rolling regression stock return on market", ("monthly_return", "market_return")),
        ("ivol_12m", "12月特质波动", "rolling residual volatility", ("monthly_return", "factor_returns")),
        ("ivol_36m", "36月特质波动", "rolling residual volatility", ("monthly_return", "factor_returns")),
        ("rev_1m", "1月反转", "lagged monthly_return", ("monthly_return",)),
        ("momentum_12_2", "12-2动量", "cumulative returns months t-12 to t-2", ("monthly_return",)),
        ("intermediate_momentum_12_7", "中期动量", "cumulative returns months t-12 to t-7", ("monthly_return",)),
        ("htp", "高到当前", "high-to-price momentum decomposition", ("high", "close")),
        ("pth", "当前到高", "price-to-high momentum decomposition", ("high", "close")),
        ("bm", "账面市值比", "book_equity / market_cap", ("equity_parent", "market_cap")),
        ("size", "规模", "log(market_cap)", ("market_cap",)),
        ("illiq", "非流动性", "amihud style illiquidity", ("return_1d", "total_turnover")),
    ]
    return [_req("P0", "monthly_research_panel", f, cn, "derived", "monthly", "monthly", "monthly research panel", formula, raw_fields, ds="derived/monthly_research_panel") for f, cn, formula, raw_fields in fields]


def _capital_flow():
    fields = ["small_order_buy_amount", "small_order_sell_amount", "small_order_net_inflow", "medium_order_buy_amount", "medium_order_sell_amount", "medium_order_net_inflow", "large_order_buy_amount", "large_order_sell_amount", "large_order_net_inflow", "extra_large_order_buy_amount", "extra_large_order_sell_amount", "extra_large_order_net_inflow", "small_order_buy_volume", "small_order_sell_volume", "total_buy_amount", "total_sell_amount", "northbound_holding_shares", "northbound_holding_market_value", "northbound_holding_ratio", "northbound_net_buy_amount", "northbound_net_buy_shares", "margin_balance", "margin_buy_amount", "margin_repay_amount", "short_balance", "short_sell_amount", "short_repay_amount", "margin_trading_balance_total"]
    derived = [("retail_oib", "散户订单不平衡", "small_order_net_inflow / total_turnover", ("small_order_net_inflow", "total_turnover")), ("small_trade_proportion", "小单占比", "small_order_buy_amount / total_buy_amount", ("small_order_buy_amount", "total_buy_amount")), ("smart_money_proxy", "聪明钱代理", "large and extra-large net inflow proxy", ("large_order_net_inflow", "extra_large_order_net_inflow"))]
    out = [_req("P1", "capital_flow_northbound_margin", f, f, "raw", "daily", "daily", "flow, leverage and investor structure", fn="capital_flow", rq_field=f, ds="capital_flow_1d") for f in fields]
    out.extend(_req("P1", "capital_flow_northbound_margin", f, cn, "derived", "daily/monthly", "derived", "flow factors", formula, raw_fields, ds="derived") for f, cn, formula, raw_fields in derived)
    return out


def _shareholder_analyst_events():
    fields = ["shareholder_count", "institutional_holding_shares", "institutional_holding_ratio", "fund_holding_shares", "fund_holding_ratio", "top10_shareholder_holding_ratio", "top10_float_shareholder_holding_ratio", "analyst_coverage_count", "rating_agency_count", "research_report_count", "consensus_eps", "consensus_net_profit", "consensus_revenue", "target_price_consensus", "rating_consensus", "earnings_announcement_date", "profit_warning_date", "profit_forecast_type", "profit_forecast_lower", "profit_forecast_upper"]
    derived = [("shareholder_count_change", "股东户数变化", "shareholder_count - lag(shareholder_count)", ("shareholder_count",)), ("shareholder_count_change_pct", "股东户数变化率", "shareholder_count / lag(shareholder_count) - 1", ("shareholder_count",))]
    out = [_req("P1", "shareholder_analyst_events", f, f, "event" if "date" in f or "forecast" in f else "raw", "quarterly/monthly/event", "PIT/monthly/event", "ownership, analyst, earnings events", fn="fundamental_events", rq_field=f, ds="shareholder_analyst_events") for f in fields]
    out.extend(_req("P1", "shareholder_analyst_events", f, cn, "derived", "quarterly/monthly", "derived", "shareholder factors", formula, raw_fields, ds="derived") for f, cn, formula, raw_fields in derived)
    return out


def _topic_fields():
    fields = ["ownership_type", "is_central_soe", "is_local_soe", "is_private", "ultimate_controller", "actual_controller_type", "invention_patent_count", "patent_application_count", "patent_grant_count", "cumulative_invention_patent_count", "esg_management_score", "esg_controversy_score", "esg_total_score", "employee_count", "rd_staff_count", "top5_supplier_purchase_amount", "total_purchase_amount", "top5_customer_sales_amount", "total_sales_amount", "bank_capital_adequacy_ratio", "bank_provision_coverage_ratio", "bank_core_tier1_capital", "broker_net_capital", "broker_risk_reserve", "broker_liquidity_coverage_ratio", "epu_index_monthly", "risk_free_rate_1y", "shibor_1m", "shibor_3m"]
    out = [_req("P2", "topic_fields", f, f, "label" if f.startswith("is_") or "ownership" in f or "controller" in f else "raw", "static/annual/monthly/quarterly", "source-specific", "thematic research", fn="topic_or_external", rq_field=f, ds="topic_fields") for f in fields]
    out.append(_req("P2", "topic_fields", "rd_staff_ratio", "研发人员占比", "derived", "annual", "derived", "thematic research", "rd_staff_count / employee_count", ("rd_staff_count", "employee_count"), ds="derived"))
    return out


def _deferred_fields():
    fields = ["level2_tick", "order_book_l2", "full_minute_bars", "baidu_index", "xueqiu_posts", "lhb_broker_seats", "new_account_openings"]
    return [_req("P3", "deferred_high_cost_fields", f, f, "raw", "high frequency/event", "defer", "deferred high-cost fields", ds="defer", notes="high_cost_or_unstable_source") for f in fields]
