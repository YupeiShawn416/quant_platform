from __future__ import annotations

import pandas as pd
import pytest

from rq_platform.paper.paper_validator import PaperValidationError, validate_target_weights


def _write_instruments(root):
    (root / "instruments").mkdir(parents=True)
    pd.DataFrame({"order_book_id": ["000001.XSHE", "600519.XSHG"]}).to_parquet(
        root / "instruments" / "instruments.parquet",
        index=False,
    )


def _write_core_coverage(root, trade_date="2026-07-14"):
    rows = [{"trade_date": trade_date, "order_book_id": "600519.XSHG", "close": 1500.0}]
    for dataset in ["prices_1d_pre", "prices_1d_none", "index_prices_1d", "tradability_1d", "valuation_1d"]:
        (root / dataset).mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_parquet(root / dataset / "year=2026.parquet", index=False)


def test_validate_target_weights_success(tmp_path):
    _write_instruments(tmp_path)
    frame = pd.DataFrame(
        [
            {"trade_date": "2026-07-10", "order_book_id": "000001.XSHE", "target_weight": 0.4},
            {"trade_date": "2026-07-10", "order_book_id": "600519.XSHG", "target_weight": 0.3},
        ]
    )

    result = validate_target_weights(frame, data_root=tmp_path)

    assert list(result.columns) == ["trade_date", "order_book_id", "target_weight"]
    assert len(result) == 2


def test_validate_target_weights_rejects_bad_sum(tmp_path):
    _write_instruments(tmp_path)
    frame = pd.DataFrame(
        [
            {"trade_date": "2026-07-10", "order_book_id": "000001.XSHE", "target_weight": 0.7},
            {"trade_date": "2026-07-10", "order_book_id": "600519.XSHG", "target_weight": 0.4},
        ]
    )

    with pytest.raises(PaperValidationError, match="exceed"):
        validate_target_weights(frame, data_root=tmp_path)


def test_validate_target_weights_rejects_unknown_symbol(tmp_path):
    _write_instruments(tmp_path)
    frame = pd.DataFrame(
        [{"trade_date": "2026-07-10", "order_book_id": "BAD.XSHG", "target_weight": 0.4}]
    )

    with pytest.raises(PaperValidationError, match="unknown"):
        validate_target_weights(frame, data_root=tmp_path)


def test_validate_target_weights_uses_dynamic_data_lake_end_date(tmp_path):
    _write_instruments(tmp_path)
    _write_core_coverage(tmp_path, trade_date="2026-07-14")
    frame = pd.DataFrame(
        [{"trade_date": "2026-07-14", "order_book_id": "600519.XSHG", "target_weight": 1.0}]
    )

    result = validate_target_weights(frame, data_root=tmp_path)

    assert result["trade_date"].tolist() == ["2026-07-14"]
