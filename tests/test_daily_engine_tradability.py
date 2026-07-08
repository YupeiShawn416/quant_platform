import pandas as pd

from rq_platform.backtest.daily_engine import DailyBacktestEngine


class TradabilityFakeDataLoader:
    def __init__(self, can_buy: bool = True, can_sell: bool = True):
        self.can_buy = can_buy
        self.can_sell = can_sell
        self.price_frame = pd.DataFrame(
            [
                {"trade_date": "2025-01-02", "order_book_id": "AAA.X", "adjust_type": "pre", "close": 10.0},
                {"trade_date": "2025-01-03", "order_book_id": "AAA.X", "adjust_type": "pre", "close": 11.0},
            ]
        )
        self.index_frame = pd.DataFrame(
            [
                {"trade_date": "2025-01-02", "order_book_id": "000300.XSHG", "close": 4000.0},
                {"trade_date": "2025-01-03", "order_book_id": "000300.XSHG", "close": 4040.0},
            ]
        )

    def load_prices(self, symbols, start, end, adjust_type="pre", fields=None):
        frame = self.price_frame[self.price_frame["order_book_id"].isin(symbols)].copy()
        if fields:
            return frame[["trade_date", "order_book_id", "adjust_type", *fields]]
        return frame

    def load_index_prices(self, index_ids=None, start_date=None, end_date=None):
        return self.index_frame[self.index_frame["order_book_id"].isin(index_ids or [])].copy()

    def load_tradability(self, symbols=None, start_date=None, end_date=None):
        return pd.DataFrame(
            [
                {
                    "trade_date": "2025-01-02",
                    "order_book_id": "AAA.X",
                    "is_listed": True,
                    "is_suspended": False,
                    "is_st": False,
                    "can_buy": self.can_buy,
                    "can_sell": self.can_sell,
                    "reason": "limit_up" if not self.can_buy else "",
                },
                {
                    "trade_date": "2025-01-03",
                    "order_book_id": "AAA.X",
                    "is_listed": True,
                    "is_suspended": False,
                    "is_st": False,
                    "can_buy": self.can_buy,
                    "can_sell": self.can_sell,
                    "reason": "limit_up" if not self.can_buy else "",
                },
            ]
        )


class NoTradabilityFakeDataLoader:
    def __init__(self):
        self.base = TradabilityFakeDataLoader(can_buy=True)

    def load_prices(self, symbols, start, end, adjust_type="pre", fields=None):
        return self.base.load_prices(symbols, start, end, adjust_type=adjust_type, fields=fields)

    def load_index_prices(self, index_ids=None, start_date=None, end_date=None):
        return self.base.load_index_prices(index_ids=index_ids, start_date=start_date, end_date=end_date)


def test_daily_engine_rejects_buy_when_not_tradable(tmp_path):
    run_dir = _run_engine(
        tmp_path,
        TradabilityFakeDataLoader(can_buy=False),
        "tradability_rejected_buy",
    )

    orders = pd.read_csv(run_dir / "orders.csv")
    trades = pd.read_csv(run_dir / "trades.csv")
    logs = (run_dir / "logs.txt").read_text(encoding="utf-8")

    assert "REJECTED" in orders["status"].tolist()
    assert orders.iloc[0]["message"] == "not tradable: limit_up"
    assert trades.empty
    assert "跳过不可交易订单" in logs


def test_daily_engine_runs_without_tradability_dataset(tmp_path):
    run_dir = _run_engine(
        tmp_path,
        NoTradabilityFakeDataLoader(),
        "tradability_missing_dataset",
    )

    trades = pd.read_csv(run_dir / "trades.csv")

    assert len(trades) == 1
    assert trades.iloc[0]["side"] == "BUY"


def _run_engine(tmp_path, data_loader, run_id):
    strategy_path = tmp_path / f"{run_id}_strategy.py"
    strategy_path.write_text(
        "def generate_weights(context, data):\n"
        "    return {'AAA.X': 1.0}\n",
        encoding="utf-8",
    )
    config = {
        "run_id": run_id,
        "strategy_name": "tradability_test",
        "start_date": "2025-01-02",
        "end_date": "2025-01-03",
        "initial_cash": 100000.0,
        "benchmark": "000300.XSHG",
        "adjust_type": "pre",
        "frequency": "daily",
        "commission_rate": 0.0003,
        "tax_rate": 0.001,
        "slippage_rate": 0.0001,
        "lot_size": 100,
        "price_field": "close",
        "output_root": str(tmp_path / "runs"),
    }
    DailyBacktestEngine(config, strategy_path, data_loader=data_loader).run()
    return tmp_path / "runs" / run_id
