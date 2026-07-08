import pandas as pd
import pytest

from rq_platform.backtest.package_formats import (
    read_weights_file,
    validate_weights_df,
    weights_long_to_wide,
    weights_wide_to_long,
)


def test_read_weights_file_csv(tmp_path):
    path = tmp_path / "weights.csv"
    _weights_df().to_csv(path, index=False)

    frame = read_weights_file(path)

    assert list(frame.columns) == ["trade_date", "order_book_id", "target_weight"]


def test_read_weights_file_parquet(tmp_path):
    path = tmp_path / "weights.parquet"
    _weights_df().to_parquet(path, index=False)

    frame = read_weights_file(path)

    assert len(frame) == 2


def test_weights_long_wide_round_trip():
    wide = weights_long_to_wide(_weights_df())
    long = weights_wide_to_long(wide)

    assert set(wide.columns) == {"trade_date", "AAA.X", "BBB.X"}
    assert long.to_dict("records") == _weights_df().to_dict("records")


def test_validate_weights_df_rejects_duplicates():
    frame = pd.concat([_weights_df(), _weights_df().head(1)])

    with pytest.raises(ValueError, match="duplicate"):
        validate_weights_df(frame, _config())


def test_validate_weights_df_rejects_negative_weight():
    frame = _weights_df()
    frame.loc[0, "target_weight"] = -0.1

    with pytest.raises(ValueError, match="negative"):
        validate_weights_df(frame, _config())


def test_validate_weights_df_rejects_overweight():
    frame = _weights_df()
    frame["target_weight"] = 0.8

    with pytest.raises(ValueError, match="exceeds"):
        validate_weights_df(frame, _config())


def test_validate_weights_df_normalizes_when_allowed():
    frame = _weights_df()
    frame["target_weight"] = 0.8
    config = {**_config(), "allow_weight_normalization": True}

    normalized, warnings = validate_weights_df(frame, config)

    assert round(normalized["target_weight"].sum(), 6) == 1.0
    assert warnings


def _weights_df():
    return pd.DataFrame(
        [
            {"trade_date": "2025-01-02", "order_book_id": "AAA.X", "target_weight": 0.5},
            {"trade_date": "2025-01-02", "order_book_id": "BBB.X", "target_weight": 0.5},
        ]
    )


def _config():
    return {"start_date": "2025-01-02", "end_date": "2025-01-31"}
