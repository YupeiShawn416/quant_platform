from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from rq_platform.backtest.package_formats import validate_weights_df
from rq_platform.factors.factor_analyzer import FactorAnalyzer
from rq_platform.factors.factor_calculator import FactorCalculator
from rq_platform.factors.factor_store import FactorStore
from rq_platform.factors.factor_weights import FactorWeightGenerator
from rq_platform.settings import settings


def _write_lake(root: Path) -> None:
    dates = pd.bdate_range("2026-05-01", periods=45).strftime("%Y-%m-%d").tolist()
    symbols = [f"00000{i}.XSHE" for i in range(1, 7)]
    price_rows = []
    valuation_rows = []
    for date_idx, trade_date in enumerate(dates):
        for symbol_idx, symbol in enumerate(symbols):
            close = 10 + symbol_idx + date_idx * (0.05 + symbol_idx * 0.01)
            price_rows.append({"trade_date": trade_date, "order_book_id": symbol, "close": close})
            valuation_rows.append(
                {
                    "trade_date": trade_date,
                    "order_book_id": symbol,
                    "market_cap": 1000 + symbol_idx * 100 + date_idx,
                    "turnover_rate": 0.01 + symbol_idx * 0.001,
                }
            )
    (root / "prices_1d_pre").mkdir(parents=True)
    pd.DataFrame(price_rows).to_parquet(root / "prices_1d_pre" / "year=2026.parquet", index=False)
    (root / "valuation_1d").mkdir(parents=True)
    pd.DataFrame(valuation_rows).to_parquet(root / "valuation_1d" / "year=2026.parquet", index=False)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        data_root = tmp_path / "data"
        factor_root = tmp_path / "factor_library"
        weights_root = tmp_path / "factor_weights"
        _write_lake(data_root)
        store = FactorStore(factor_root)
        calculator = FactorCalculator(data_root=data_root, store=store)
        calculator.compute(["market_cap", "momentum_20d"], "2026-05-01", "2026-06-30", overwrite=True)
        summary = FactorAnalyzer(data_root=data_root, store=store).analyze("momentum_20d")
        weights = FactorWeightGenerator(store=store, output_root=weights_root).generate("momentum_20d", top_quantile=0.4, max_names=3)
        frame = pd.read_csv(weights["target_weights"])
        assert not frame.empty
        assert (frame["target_weight"] >= 0).all()
        assert (frame.groupby("trade_date")["target_weight"].sum() <= 1.000001).all()
        validate_weights_df(
            frame,
            {
                "start_date": "2026-05-01",
                "end_date": "2026-06-30",
                "lot_size": 100,
            },
        )

        settings.factor_library_dir = str(factor_root)
        settings.factor_weights_dir = str(weights_root)
        settings.api_token = "change_me"
        from rq_platform.api.main import app

        client = TestClient(app)
        assert client.get("/ui/factors").status_code == 200
        assert client.get("/ui/factors/momentum_20d").status_code == 200
        assert client.get("/factors").status_code == 200
        print(f"summary_factor={summary['factor_id']}")
        print(f"weights_rows={weights['row_count']}")
        print("factor smoke local passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
