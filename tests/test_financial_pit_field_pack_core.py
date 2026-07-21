import pandas as pd

from rq_platform.etl.financial_pit_field_pack_core import (
    fetch_financial_pit_field_pack,
    normalize_financial_pit_field_pack,
    run_financial_pit_field_pack_backfill,
    write_financial_pit_field_pack,
)
from rq_platform.etl.financial_pit_field_pack_plan import FinancialPitField, FinancialPitFieldPackTask


FIELDS = [FinancialPitField("revenue", "get_pit_financials_ex", "revenue")]


class FakeRQData:
    def __init__(self):
        self.called = False

    def get_pit_financials_ex(self, **kwargs):
        self.called = True
        return pd.DataFrame(
            {
                "order_book_id": ["000001.XSHE"],
                "quarter": ["2024q4"],
                "info_date": ["2025-03-20"],
                "rice_create_tm": ["2025-03-20 10:00:00"],
                "if_adjusted": [False],
                "revenue": [100.0],
            }
        ).set_index(["order_book_id", "quarter", "info_date", "rice_create_tm", "if_adjusted"])


def test_dry_run_does_not_call_rqdata():
    task = FinancialPitFieldPackTask(
        start_date="2024-01-01",
        end_date="2025-12-31",
        start_quarter="2024q1",
        end_quarter="2025q4",
        symbols=["000001.XSHE"],
        fields=FIELDS,
        batch_size=1,
        dry_run=True,
        overwrite=False,
    )

    result = run_financial_pit_field_pack_backfill(task, confirm=False)

    assert result["status"] == "dry_run"
    assert result["expected_api_calls"] == 1


def test_fetch_and_normalize_canonical_mapping():
    fake = FakeRQData()

    frame = fetch_financial_pit_field_pack(fake, ["000001.XSHE"], FIELDS, "2024q4", "2024q4")

    assert fake.called
    assert list(frame["report_period"]) == ["2024q4"]
    assert "info_date" in frame.columns
    assert "field_mapping_json" in frame.columns
    assert frame["revenue"].iloc[0] == 100.0


def test_append_and_deduplicate(tmp_path, monkeypatch):
    import rq_platform.etl.financial_pit_field_pack_core as core

    monkeypatch.setattr(core.settings, "data_root", str(tmp_path))
    frame = normalize_financial_pit_field_pack(
        pd.DataFrame(
            {
                "order_book_id": ["000001.XSHE", "000001.XSHE"],
                "quarter": ["2024q4", "2024q4"],
                "info_date": ["2025-03-20", "2025-03-20"],
                "rice_create_tm": ["2025-03-20 10:00:00", "2025-03-20 10:00:00"],
                "if_adjusted": [False, False],
                "revenue": [100.0, 101.0],
            }
        ),
        FIELDS,
    )

    paths = write_financial_pit_field_pack(frame, overwrite=False)
    written = pd.read_parquet(paths[0])

    assert len(written) == 1
    assert written["revenue"].iloc[0] == 101.0
