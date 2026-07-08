from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd

from rq_platform.backtest.result_schema import (
    CHARTS_JSON,
    CONFIG_JSON,
    DAILY_ACCOUNT_COLUMNS,
    DAILY_ACCOUNT_CSV,
    LOGS_TXT,
    MANIFEST_JSON,
    MONTHLY_RETURNS_CSV,
    NAV_COLUMNS,
    NAV_CSV,
    ORDERS_COLUMNS,
    ORDERS_CSV,
    POSITIONS_COLUMNS,
    POSITIONS_CSV,
    ROLLING_METRICS_CSV,
    SUMMARY_CSV,
    SUMMARY_FIELDS,
    SUMMARY_JSON,
    TRADES_COLUMNS,
    TRADES_CSV,
)
from rq_platform.backtest.result_store import BacktestResultStore
from rq_platform.backtest.strategy_loader import load_strategy_module
from rq_platform.data.data_loader import ResearchDataLoader
from rq_platform.metrics import calculate_performance_metrics


DEFAULTS = {
    "adjust_type": "pre",
    "frequency": "daily",
    "commission_rate": 0.0003,
    "tax_rate": 0.001,
    "slippage_rate": 0.0001,
    "lot_size": 100,
    "price_field": "close",
    "output_root": "runs/backtests",
}


@dataclass
class BacktestData:
    current_date: str
    history: pd.DataFrame
    current_prices: dict[str, float]
    price_field: str = "close"

    def get_price(self, symbol: str, field: str = "close") -> float | None:
        if field != self.price_field:
            rows = self.history[
                (self.history["order_book_id"] == symbol)
                & (self.history["trade_date"] == self.current_date)
            ]
            if rows.empty or field not in rows.columns:
                return None
            return _safe_float(rows.iloc[-1][field])
        return self.current_prices.get(symbol)

    def get_history(self, symbol: str, fields: str | list[str], window: int) -> pd.DataFrame:
        field_list = [fields] if isinstance(fields, str) else list(fields)
        columns = ["trade_date", *field_list]
        symbol_history = self.history[self.history["order_book_id"] == symbol].tail(window)
        available = [column for column in columns if column in symbol_history.columns]
        return symbol_history[available].reset_index(drop=True)


class DailyBacktestEngine:
    def __init__(
        self,
        config: dict[str, Any],
        strategy_path: str | Path,
        data_loader=None,
    ):
        merged = {**DEFAULTS, **config}
        self.config = merged
        self.strategy_path = Path(strategy_path)
        self.data_loader = data_loader or ResearchDataLoader()
        self.logs: list[str] = []

    def run(self) -> dict[str, Any]:
        self._validate_config()
        run_id = str(self.config["run_id"])
        strategy = load_strategy_module(self.strategy_path)
        symbols = self._resolve_symbols(strategy)
        if not symbols:
            raise ValueError("strategy returned no symbols during bootstrap; add config.symbols for V0")

        price_field = str(self.config["price_field"])
        prices = self._load_prices(symbols, price_field)
        if prices.empty:
            raise ValueError("no local price data found for strategy symbols")

        benchmark_nav = self._load_benchmark_nav(prices["trade_date"].tolist())
        frames = self._simulate(strategy, prices, benchmark_nav)
        self.logs.append(f"回测完成 run_id={run_id}")
        result = self._write_result_bundle(frames)
        return result

    def _validate_config(self) -> None:
        required = ["run_id", "strategy_name", "start_date", "end_date", "initial_cash"]
        missing = [key for key in required if key not in self.config]
        if missing:
            raise ValueError(f"missing backtest config fields: {', '.join(missing)}")
        if self.config.get("frequency") != "daily":
            raise ValueError("DailyBacktestEngine V0 only supports frequency=daily")
        if float(self.config["initial_cash"]) <= 0:
            raise ValueError("initial_cash must be positive")

    def _resolve_symbols(self, strategy) -> list[str]:
        configured = self.config.get("symbols")
        if configured:
            return _unique_symbols(configured)
        data = BacktestData(
            current_date=str(self.config["start_date"]),
            history=pd.DataFrame(),
            current_prices={},
            price_field=str(self.config["price_field"]),
        )
        context = SimpleNamespace(
            current_date=str(self.config["start_date"]),
            portfolio={},
            config=self.config,
            trading_dates=[],
            previous_positions={},
        )
        weights = strategy.generate_weights(context, data) or {}
        return _unique_symbols(weights.keys())

    def _load_prices(self, symbols: list[str], price_field: str) -> pd.DataFrame:
        self.logs.append(
            f"读取本地 Parquet 行情 symbols={len(symbols)} "
            f"start={self.config['start_date']} end={self.config['end_date']}"
        )
        frame = self.data_loader.load_prices(
            symbols=symbols,
            start=str(self.config["start_date"]),
            end=str(self.config["end_date"]),
            adjust_type=str(self.config["adjust_type"]),
            fields=[price_field],
        )
        if frame.empty:
            return frame
        required = {"trade_date", "order_book_id", price_field}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"price data missing required columns: {sorted(missing)}")
        frame = frame.copy()
        frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
        frame[price_field] = pd.to_numeric(frame[price_field], errors="coerce")
        frame = frame.dropna(subset=[price_field])
        frame = frame.sort_values(["trade_date", "order_book_id"]).reset_index(drop=True)
        return frame

    def _load_benchmark_nav(self, trading_dates: list[str]) -> dict[str, float]:
        benchmark = self.config.get("benchmark")
        if not benchmark:
            self.logs.append("未配置 benchmark，benchmark_nav 使用 1.0")
            return {date: 1.0 for date in trading_dates}
        frame = self.data_loader.load_prices(
            symbols=[str(benchmark)],
            start=str(self.config["start_date"]),
            end=str(self.config["end_date"]),
            adjust_type=str(self.config["adjust_type"]),
            fields=[str(self.config["price_field"])],
        )
        price_field = str(self.config["price_field"])
        if frame.empty or price_field not in frame.columns:
            self.logs.append(f"benchmark {benchmark} 无本地价格，benchmark_nav 使用 1.0")
            return {date: 1.0 for date in trading_dates}
        frame = frame.copy()
        frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
        frame[price_field] = pd.to_numeric(frame[price_field], errors="coerce")
        frame = frame.dropna(subset=[price_field]).sort_values("trade_date")
        if frame.empty:
            self.logs.append(f"benchmark {benchmark} 价格为空，benchmark_nav 使用 1.0")
            return {date: 1.0 for date in trading_dates}
        base = float(frame[price_field].iloc[0])
        nav = {
            row.trade_date: float(row._asdict()[price_field]) / base
            for row in frame.itertuples(index=False)
        }
        return {date: nav.get(date, 1.0) for date in trading_dates}

    def _simulate(self, strategy, prices: pd.DataFrame, benchmark_nav: dict[str, float]):
        run_id = str(self.config["run_id"])
        self.logs.append(f"回测开始 run_id={run_id} strategy={self.config['strategy_name']}")
        self.logs.append(f"配置 {self._public_config()}")

        price_field = str(self.config["price_field"])
        initial_cash = float(self.config["initial_cash"])
        cash = initial_cash
        positions: dict[str, int] = {}
        previous_total = initial_cash
        trading_dates = sorted(prices["trade_date"].unique().tolist())
        all_symbols = sorted(prices["order_book_id"].unique().tolist())

        nav_rows = []
        account_rows = []
        position_rows = []
        trade_rows = []
        order_rows = []

        for trade_date in trading_dates:
            history = prices[prices["trade_date"] <= trade_date]
            day_prices = (
                prices[prices["trade_date"] == trade_date]
                .set_index("order_book_id")[price_field]
                .to_dict()
            )
            current_prices = {
                symbol: float(day_prices[symbol])
                for symbol in all_symbols
                if symbol in day_prices and _is_valid_price(day_prices[symbol])
            }
            portfolio = self._portfolio_snapshot(cash, positions, current_prices)
            data = BacktestData(trade_date, history, current_prices, price_field)
            context = SimpleNamespace(
                current_date=trade_date,
                portfolio=portfolio,
                config=self.config,
                trading_dates=trading_dates,
                previous_positions=positions.copy(),
            )
            raw_weights = strategy.generate_weights(context, data) or {}
            weights = self._normalize_weights(raw_weights)
            self.logs.append(f"每日调仓 trade_date={trade_date} weights={weights}")

            total_before = self._total_value(cash, positions, current_prices)
            cash, positions = self._rebalance(
                trade_date=trade_date,
                total_value=total_before,
                cash=cash,
                positions=positions,
                weights=weights,
                prices=current_prices,
                trade_rows=trade_rows,
                order_rows=order_rows,
            )

            market_value = self._market_value(positions, current_prices)
            total_value = cash + market_value
            daily_pnl = total_value - previous_total
            daily_return = daily_pnl / previous_total if previous_total else 0.0
            strategy_nav = total_value / initial_cash
            bench_nav = benchmark_nav.get(trade_date, 1.0)
            bench_prev = benchmark_nav.get(_previous_date(trading_dates, trade_date), bench_nav)
            benchmark_return = bench_nav / bench_prev - 1 if bench_prev else 0.0
            drawdown = _drawdown_after(nav_rows, strategy_nav)

            nav_rows.append(
                {
                    "trade_date": trade_date,
                    "strategy_nav": strategy_nav,
                    "benchmark_nav": bench_nav,
                    "excess_nav": strategy_nav / bench_nav if bench_nav else None,
                    "daily_return": daily_return,
                    "benchmark_return": benchmark_return,
                    "excess_return": daily_return - benchmark_return,
                    "drawdown": drawdown,
                }
            )
            account_rows.append(
                {
                    "trade_date": trade_date,
                    "total_value": total_value,
                    "cash": cash,
                    "market_value": market_value,
                    "position_ratio": market_value / total_value if total_value else 0.0,
                    "daily_pnl": daily_pnl,
                    "daily_return": daily_return,
                }
            )
            for symbol, quantity in sorted(positions.items()):
                close = current_prices.get(symbol)
                if close is None:
                    continue
                value = quantity * close
                position_rows.append(
                    {
                        "trade_date": trade_date,
                        "order_book_id": symbol,
                        "symbol": symbol,
                        "quantity": quantity,
                        "close": close,
                        "market_value": value,
                        "weight": value / total_value if total_value else 0.0,
                        "pnl": 0.0,
                    }
                )
            previous_total = total_value

        return {
            "nav": pd.DataFrame(nav_rows, columns=NAV_COLUMNS),
            "daily_account": pd.DataFrame(account_rows, columns=DAILY_ACCOUNT_COLUMNS),
            "positions": pd.DataFrame(position_rows, columns=POSITIONS_COLUMNS),
            "trades": pd.DataFrame(trade_rows, columns=TRADES_COLUMNS),
            "orders": pd.DataFrame(order_rows, columns=ORDERS_COLUMNS),
        }

    def _rebalance(
        self,
        trade_date: str,
        total_value: float,
        cash: float,
        positions: dict[str, int],
        weights: dict[str, float],
        prices: dict[str, float],
        trade_rows: list[dict[str, Any]],
        order_rows: list[dict[str, Any]],
    ) -> tuple[float, dict[str, int]]:
        lot_size = int(self.config["lot_size"])
        target_quantities: dict[str, int] = {}
        for symbol, weight in weights.items():
            price = prices.get(symbol)
            if not _is_valid_price(price):
                self.logs.append(f"跳过无价格标的 trade_date={trade_date} symbol={symbol}")
                continue
            target_value = total_value * weight
            target_quantities[symbol] = _floor_to_lot(target_value / float(price), lot_size)

        symbols = sorted(set(positions) | set(target_quantities))
        sell_symbols = [
            symbol
            for symbol in symbols
            if positions.get(symbol, 0) > target_quantities.get(symbol, 0)
        ]
        buy_symbols = [
            symbol
            for symbol in symbols
            if target_quantities.get(symbol, 0) > positions.get(symbol, 0)
        ]

        for symbol in sell_symbols:
            quantity = positions.get(symbol, 0) - target_quantities.get(symbol, 0)
            cash = self._execute_order(
                trade_date, symbol, "SELL", quantity, prices, cash, positions, trade_rows, order_rows
            )
        for symbol in buy_symbols:
            quantity = target_quantities.get(symbol, 0) - positions.get(symbol, 0)
            cash = self._execute_order(
                trade_date, symbol, "BUY", quantity, prices, cash, positions, trade_rows, order_rows
            )
        return cash, {symbol: qty for symbol, qty in positions.items() if qty > 0}

    def _execute_order(
        self,
        trade_date: str,
        symbol: str,
        side: str,
        quantity: int,
        prices: dict[str, float],
        cash: float,
        positions: dict[str, int],
        trade_rows: list[dict[str, Any]],
        order_rows: list[dict[str, Any]],
    ) -> float:
        lot_size = int(self.config["lot_size"])
        price = prices.get(symbol)
        if quantity <= 0 or not _is_valid_price(price):
            return cash
        quantity = _floor_to_lot(quantity, lot_size)
        if quantity <= 0:
            return cash

        slippage_rate = float(self.config["slippage_rate"])
        commission_rate = float(self.config["commission_rate"])
        tax_rate = float(self.config["tax_rate"])
        execution_price = float(price) * (1 + slippage_rate if side == "BUY" else 1 - slippage_rate)
        amount = execution_price * quantity
        commission = amount * commission_rate
        tax = amount * tax_rate if side == "SELL" else 0.0
        slippage = abs(float(price) - execution_price) * quantity
        status = "FILLED"
        message = "filled"

        if side == "BUY":
            total_cost = amount + commission
            if total_cost > cash:
                max_quantity = _floor_to_lot(cash / (execution_price * (1 + commission_rate)), lot_size)
                if max_quantity <= 0:
                    self.logs.append(f"资金不足 trade_date={trade_date} symbol={symbol}")
                    self._record_order(order_rows, trade_date, symbol, side, quantity, execution_price, "REJECTED", "insufficient cash")
                    return cash
                quantity = max_quantity
                amount = execution_price * quantity
                commission = amount * commission_rate
                total_cost = amount + commission
                status = "PARTIAL_FILLED"
                message = "shrunk by cash"
                self.logs.append(f"资金不足缩量 trade_date={trade_date} symbol={symbol} quantity={quantity}")
            cash -= total_cost
            positions[symbol] = positions.get(symbol, 0) + quantity
        else:
            quantity = min(quantity, positions.get(symbol, 0))
            quantity = _floor_to_lot(quantity, lot_size)
            if quantity <= 0:
                return cash
            amount = execution_price * quantity
            commission = amount * commission_rate
            tax = amount * tax_rate
            slippage = abs(float(price) - execution_price) * quantity
            cash += amount - commission - tax
            positions[symbol] = positions.get(symbol, 0) - quantity

        self._record_order(order_rows, trade_date, symbol, side, quantity, execution_price, status, message)
        trade_rows.append(
            {
                "trade_date": trade_date,
                "datetime": f"{trade_date} 15:00:00",
                "order_book_id": symbol,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": execution_price,
                "amount": amount,
                "commission": commission,
                "tax": tax,
                "slippage": slippage,
                "realized_pnl": 0.0,
            }
        )
        self.logs.append(
            f"成交 trade_date={trade_date} symbol={symbol} side={side} "
            f"quantity={quantity} price={execution_price:.4f}"
        )
        return cash

    def _record_order(
        self,
        order_rows: list[dict[str, Any]],
        trade_date: str,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        status: str,
        message: str,
    ) -> None:
        order_rows.append(
            {
                "trade_date": trade_date,
                "datetime": f"{trade_date} 14:59:59",
                "order_book_id": symbol,
                "side": side,
                "order_type": "MARKET",
                "quantity": quantity,
                "price": price,
                "status": status,
                "message": message,
            }
        )
        self.logs.append(
            f"下单 trade_date={trade_date} symbol={symbol} side={side} quantity={quantity} status={status}"
        )

    def _write_result_bundle(self, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
        store = BacktestResultStore(root=self.config["output_root"])
        run_id = str(self.config["run_id"])
        run_dir = store.create_run_dir(run_id)
        created_at = datetime.now().isoformat(timespec="seconds")
        metrics = calculate_performance_metrics(frames["nav"])
        final_value = float(frames["daily_account"]["total_value"].iloc[-1])
        summary = {
            "run_id": run_id,
            "strategy_name": self.config["strategy_name"],
            "start_date": self.config["start_date"],
            "end_date": self.config["end_date"],
            "initial_cash": self.config["initial_cash"],
            "final_value": final_value,
            "trade_count": int(len(frames["trades"])),
            "created_at": created_at,
            **metrics,
        }
        summary = {field: _safe_json_value(summary.get(field)) for field in SUMMARY_FIELDS}
        files = [
            MANIFEST_JSON,
            CONFIG_JSON,
            SUMMARY_JSON,
            SUMMARY_CSV,
            NAV_CSV,
            DAILY_ACCOUNT_CSV,
            POSITIONS_CSV,
            TRADES_CSV,
            ORDERS_CSV,
            LOGS_TXT,
            MONTHLY_RETURNS_CSV,
            ROLLING_METRICS_CSV,
            CHARTS_JSON,
        ]
        manifest = {
            "run_id": run_id,
            "strategy_name": self.config["strategy_name"],
            "engine": "daily_engine_v0",
            "created_at": created_at,
            "files": files,
        }
        charts = {
            "nav": frames["nav"][["trade_date", "strategy_nav", "benchmark_nav", "excess_nav"]].to_dict("records"),
            "drawdown": frames["nav"][["trade_date", "drawdown"]].to_dict("records"),
        }
        monthly_returns = _monthly_returns(frames["nav"])
        rolling_metrics = _rolling_metrics(frames["nav"])

        store.write_json(run_dir, MANIFEST_JSON, manifest)
        store.write_json(run_dir, CONFIG_JSON, self._public_config())
        store.write_json(run_dir, SUMMARY_JSON, summary)
        store.write_csv(run_dir, SUMMARY_CSV, pd.DataFrame([summary], columns=SUMMARY_FIELDS))
        store.write_csv(run_dir, NAV_CSV, frames["nav"][NAV_COLUMNS])
        store.write_csv(run_dir, DAILY_ACCOUNT_CSV, frames["daily_account"][DAILY_ACCOUNT_COLUMNS])
        store.write_csv(run_dir, POSITIONS_CSV, frames["positions"][POSITIONS_COLUMNS])
        store.write_csv(run_dir, TRADES_CSV, frames["trades"][TRADES_COLUMNS])
        store.write_csv(run_dir, ORDERS_CSV, frames["orders"][ORDERS_COLUMNS])
        store.write_csv(run_dir, MONTHLY_RETURNS_CSV, monthly_returns)
        store.write_csv(run_dir, ROLLING_METRICS_CSV, rolling_metrics)
        store.write_json(run_dir, CHARTS_JSON, charts)
        (run_dir / LOGS_TXT).write_text("\n".join(self.logs) + "\n", encoding="utf-8")
        zip_path = store.package_zip(run_id)
        return {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "zip_path": str(zip_path),
            "summary": summary,
        }

    def _normalize_weights(self, weights: dict[str, Any]) -> dict[str, float]:
        clean: dict[str, float] = {}
        for symbol, value in weights.items():
            weight = _safe_float(value)
            if weight is None or weight <= 0:
                continue
            clean[str(symbol)] = weight
        total = sum(clean.values())
        if total > 1.0:
            self.logs.append(f"权重总和 {total:.6f} 超过 1.0，已等比例缩放")
            return {symbol: weight / total for symbol, weight in clean.items()}
        return clean

    def _portfolio_snapshot(
        self, cash: float, positions: dict[str, int], prices: dict[str, float]
    ) -> dict[str, Any]:
        market_value = self._market_value(positions, prices)
        total_value = cash + market_value
        return {
            "cash": cash,
            "positions": positions.copy(),
            "market_value": market_value,
            "total_value": total_value,
            "position_ratio": market_value / total_value if total_value else 0.0,
        }

    def _market_value(self, positions: dict[str, int], prices: dict[str, float]) -> float:
        return sum(quantity * prices.get(symbol, 0.0) for symbol, quantity in positions.items())

    def _total_value(self, cash: float, positions: dict[str, int], prices: dict[str, float]) -> float:
        return cash + self._market_value(positions, prices)

    def _public_config(self) -> dict[str, Any]:
        return {key: value for key, value in self.config.items() if "token" not in key.lower()}


def _unique_symbols(symbols) -> list[str]:
    return sorted({str(symbol) for symbol in symbols if str(symbol).strip()})


def _safe_float(value) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def _safe_json_value(value):
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _is_valid_price(value) -> bool:
    price = _safe_float(value)
    return price is not None and price > 0


def _floor_to_lot(quantity: float, lot_size: int) -> int:
    if lot_size <= 1:
        return max(int(quantity), 0)
    return max(int(quantity // lot_size) * lot_size, 0)


def _previous_date(trading_dates: list[str], trade_date: str) -> str | None:
    index = trading_dates.index(trade_date)
    if index == 0:
        return None
    return trading_dates[index - 1]


def _drawdown_after(nav_rows: list[dict[str, Any]], strategy_nav: float) -> float:
    historical = [row["strategy_nav"] for row in nav_rows]
    high = max([strategy_nav, *historical])
    return strategy_nav / high - 1 if high else 0.0


def _monthly_returns(nav: pd.DataFrame) -> pd.DataFrame:
    if nav.empty:
        return pd.DataFrame(columns=["month", "monthly_return"])
    frame = nav.copy()
    frame["month"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m")
    result = (
        frame.groupby("month", as_index=False)["daily_return"]
        .apply(lambda values: (1 + values).prod() - 1)
        .rename(columns={"daily_return": "monthly_return"})
    )
    return result


def _rolling_metrics(nav: pd.DataFrame) -> pd.DataFrame:
    if nav.empty:
        return pd.DataFrame(columns=["trade_date", "rolling_20_return", "rolling_20_volatility"])
    frame = nav[["trade_date", "strategy_nav", "daily_return"]].copy()
    return pd.DataFrame(
        {
            "trade_date": frame["trade_date"],
            "rolling_20_return": frame["strategy_nav"].pct_change(20).fillna(0),
            "rolling_20_volatility": (
                frame["daily_return"].rolling(20).std(ddof=0).fillna(0) * math.sqrt(252)
            ),
        }
    )
