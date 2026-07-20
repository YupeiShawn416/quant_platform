import json

import pandas as pd

from rq_platform.etl.hxz_data_audit import build_hxz_audit, write_hxz_audit_outputs


def _write_parquet(path, frame):
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)


def test_hxz_audit_identifies_financial_statement_gaps(tmp_path):
    root = tmp_path / "rqdata"
    _write_parquet(
        root / "prices_1d_none" / "year=2026.parquet",
        pd.DataFrame(
            {
                "trade_date": ["2026-07-10"],
                "order_book_id": ["000001.XSHE"],
                "adjust_type": ["none"],
                "close": [10.0],
            }
        ),
    )
    _write_parquet(
        root / "valuation_1d" / "year=2026.parquet",
        pd.DataFrame(
            {
                "trade_date": ["2026-07-10"],
                "order_book_id": ["000001.XSHE"],
                "market_cap": [100.0],
                "float_market_cap": [80.0],
            }
        ),
    )
    _write_parquet(
        root / "tradability_1d" / "year=2026.parquet",
        pd.DataFrame(
            {
                "trade_date": ["2026-07-10"],
                "order_book_id": ["000001.XSHE"],
                "is_listed": [True],
            }
        ),
    )
    _write_parquet(
        root / "industry_classification" / "year=2026.parquet",
        pd.DataFrame(
            {
                "trade_date": ["2026-07-10"],
                "order_book_id": ["000001.XSHE"],
                "industry_system": ["citics_2019"],
                "industry_level": [1],
                "industry_name": ["银行"],
            }
        ),
    )

    audit = build_hxz_audit(root)

    assert audit["local_readiness"]["ready_for_full_hxz_replication"] is False
    requirements = {item["requirement"]: item for item in audit["hxz_field_matrix"]}
    assert requirements["previous_month_end_market_cap"]["local_status"] == "available"
    assert requirements["annual_total_assets"]["local_status"] == "missing"
    assert requirements["single_quarter_profit"]["priority"] == "P0"


def test_hxz_audit_outputs_reports_and_manifest(tmp_path):
    root = tmp_path / "rqdata"
    _write_parquet(
        root / "trading_calendar" / "trading_calendar.parquet",
        pd.DataFrame({"trade_date": ["2026-07-10"], "is_open": [True]}),
    )
    audit = build_hxz_audit(root)
    outputs = write_hxz_audit_outputs(
        audit,
        output_dir=tmp_path / "reports",
        manifest_dir=tmp_path / "manifests",
    )

    assert outputs["audit_json"].exists()
    assert outputs["audit_md"].exists()
    assert outputs["field_matrix_csv"].exists()
    manifest = json.loads(outputs["backfill_manifest_json"].read_text())
    assert manifest["status"] == "draft_pending_rqdata_probe"
