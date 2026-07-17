from pathlib import Path

import pandas as pd

from factor_pool.data_adapter.control_backfill import backfill_quarterly_controls, build_quarter_control_frame


class FakeProvider:
    def trading_date(self, quarter_end):
        return "2025-12-31"

    def components(self, date):
        return ["A.X", "B.X"]

    def industry(self, ids, date):
        return pd.DataFrame({"order_book_id": ids, "industry_code": ["bank", "tech"], "industry_name": ["Bank", "Tech"]})

    def valuation(self, ids, date):
        return pd.DataFrame({"order_book_id": ids, "float_market_cap": [100.0, 200.0]})

    def statuses(self, ids, date):
        return pd.DataFrame({
            "order_book_id": ids,
            "is_st": [False, True],
            "is_suspended": [False, False],
            "close": [10.0, 20.0],
            "limit_up": [11.0, 20.0],
            "limit_down": [9.0, 18.0],
        })

    def listing(self, ids, date):
        return pd.DataFrame({
            "order_book_id": ids,
            "is_listed": [True, True],
            "listed_days": [1000, 2000],
        })


def test_build_quarter_control_frame_normalizes_controls():
    frame = build_quarter_control_frame(
        FakeProvider(),
        "2025-12-31",
        minimum_components=1,
        maximum_components=3,
    )
    keyed = frame.set_index("order_book_id")

    assert len(frame) == 2
    assert keyed.loc["A.X", "industry_code"] == "bank"
    assert keyed.loc["B.X", "float_market_cap"] == 200.0
    assert bool(keyed.loc["B.X", "is_st"]) is True
    assert bool(keyed.loc["B.X", "is_limit_up"]) is True
    assert keyed.loc["A.X", "listed_days"] == 1000


def test_backfill_quarterly_controls_is_resumable(tmp_path):
    first = backfill_quarterly_controls(
        FakeProvider(),
        quarter_ends=["2025-12-31"],
        output_root=tmp_path,
        minimum_components=1,
        maximum_components=3,
    )
    second = backfill_quarterly_controls(
        FakeProvider(),
        quarter_ends=["2025-12-31"],
        output_root=tmp_path,
        minimum_components=1,
        maximum_components=3,
    )

    assert first == {"written": 1, "cached": 0, "failed": 0, "rows": 2}
    assert second == {"written": 0, "cached": 1, "failed": 0, "rows": 2}
    assert (tmp_path / "date=2025-12-31" / "controls.parquet").is_file()
