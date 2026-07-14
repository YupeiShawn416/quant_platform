from __future__ import annotations

import math
from typing import Any

import pandas as pd

from rq_platform.data.query_service import DataQueryError, DataQueryService
from rq_platform.paper.paper_account import PaperAccount, utc_now_iso
from rq_platform.paper.paper_metrics import max_drawdown, total_return
from rq_platform.paper.paper_registry import PaperAccountRegistry
from rq_platform.paper.paper_store import PaperAccountStore


class PaperEngineError(RuntimeError):
    pass


class PaperEngine:
    def __init__(
        self,
        store: PaperAccountStore | None = None,
        registry: PaperAccountRegistry | None = None,
        query_service: DataQueryService | None = None,
        lot_size: int = 100,
        cost_rate: float = 0.0002,
    ):
        self.store = store or PaperAccountStore()
        self.registry = registry or PaperAccountRegistry()
        self.query_service = query_service or DataQueryService()
        self.lot_size = lot_size
        self.cost_rate = cost_rate

    def run_daily(self, paper_id: str, trade_date: str) -> dict[str, Any]:
        account = self.store.read_account(paper_id)
        if account.status != "active":
            raise PaperEngineError(f"paper account is not active: {account.status}")

        weights = self.store.read_csv(account.paper_id, "target_weights.csv")
        weights = weights[weights["trade_date"].astype(str) == trade_date].copy()
        prior_positions = self._latest_positions(account.paper_id, before_or_on=trade_date)
        symbols = sorted(set(prior_positions) | set(weights.get("order_book_id", pd.Series(dtype=str)).astype(str)))
        if not symbols:
            return self._record_no_position_day(account, trade_date)

        prices = self._load_prices(trade_date, symbols)
        tradable = self._load_tradability(trade_date, symbols)
        missing_prices = [symbol for symbol in symbols if symbol not in prices]
        if missing_prices:
            raise PaperEngineError(f"missing close price for {missing_prices[0]} on {trade_date}")

        cash = self._latest_cash(account.paper_id, default=float(account.cash or account.initial_cash))
        market_value = sum(quantity * prices[symbol] for symbol, quantity in prior_positions.items())
        total_value_before = cash + market_value

        target_weights = {str(row.order_book_id): float(row.target_weight) for row in weights.itertuples()}
        target_positions = self._target_positions(total_value_before, target_weights, prices)
        cash, positions, orders, trades = self._rebalance(
            trade_date=trade_date,
            cash=cash,
            current_positions=prior_positions,
            target_positions=target_positions,
            prices=prices,
            tradable=tradable,
        )

        final_market_value = sum(quantity * prices[symbol] for symbol, quantity in positions.items())
        total_value = cash + final_market_value
        nav = total_value / float(account.initial_cash)
        position_rows = self._position_rows(trade_date, positions, prices, total_value)

        self.store.append_csv(account.paper_id, "orders.csv", orders)
        self.store.append_csv(account.paper_id, "trades.csv", trades)
        self.store.write_csv(account.paper_id, "positions.csv", self._replace_trade_date("positions.csv", account.paper_id, trade_date, position_rows))
        self.store.write_csv(
            account.paper_id,
            "daily_account.csv",
            self._replace_trade_date(
                "daily_account.csv",
                account.paper_id,
                trade_date,
                [{"trade_date": trade_date, "cash": cash, "market_value": final_market_value, "total_value": total_value, "nav": nav}],
            ),
        )
        self.store.write_csv(
            account.paper_id,
            "nav.csv",
            self._replace_trade_date(
                "nav.csv",
                account.paper_id,
                trade_date,
                [{"trade_date": trade_date, "nav": nav, "total_value": total_value}],
            ),
        )

        nav_frame = self.store.read_csv(account.paper_id, "nav.csv")
        account.cash = cash
        account.latest_trade_date = trade_date
        account.current_nav = nav
        account.total_return = total_return(nav_frame["nav"])
        account.max_drawdown = max_drawdown(nav_frame["nav"])
        account.updated_at = utc_now_iso()
        self.store.write_account(account)
        self.registry.upsert(account)
        self.store.append_log(
            account.paper_id,
            {
                "created_at": utc_now_iso(),
                "level": "info",
                "event": "run_daily",
                "trade_date": trade_date,
                "orders": len(orders),
                "trades": len(trades),
                "nav": nav,
            },
        )
        return {
            "status": "success",
            "paper_id": account.paper_id,
            "trade_date": trade_date,
            "nav": nav,
            "total_value": total_value,
            "orders": len(orders),
            "trades": len(trades),
        }

    def _record_no_position_day(self, account: PaperAccount, trade_date: str) -> dict[str, Any]:
        cash = self._latest_cash(account.paper_id, default=float(account.cash or account.initial_cash))
        nav = cash / float(account.initial_cash)
        self.store.write_csv(
            account.paper_id,
            "daily_account.csv",
            self._replace_trade_date(
                "daily_account.csv",
                account.paper_id,
                trade_date,
                [{"trade_date": trade_date, "cash": cash, "market_value": 0.0, "total_value": cash, "nav": nav}],
            ),
        )
        self.store.write_csv(
            account.paper_id,
            "nav.csv",
            self._replace_trade_date("nav.csv", account.paper_id, trade_date, [{"trade_date": trade_date, "nav": nav, "total_value": cash}]),
        )
        account.latest_trade_date = trade_date
        account.current_nav = nav
        account.updated_at = utc_now_iso()
        self.store.write_account(account)
        self.registry.upsert(account)
        return {"status": "success", "paper_id": account.paper_id, "trade_date": trade_date, "nav": nav, "orders": 0, "trades": 0}

    def _load_prices(self, trade_date: str, symbols: list[str]) -> dict[str, float]:
        try:
            frame, _ = self.query_service.query(
                "prices_1d_pre",
                start_date=trade_date,
                end_date=trade_date,
                order_book_ids=symbols,
                fields=["trade_date", "order_book_id", "close"],
                limit=50000,
            )
        except DataQueryError as exc:
            raise PaperEngineError(str(exc)) from exc
        return {str(row.order_book_id): float(row.close) for row in frame.itertuples() if not pd.isna(row.close)}

    def _load_tradability(self, trade_date: str, symbols: list[str]) -> dict[str, dict[str, bool]]:
        try:
            frame, _ = self.query_service.query(
                "tradability_1d",
                start_date=trade_date,
                end_date=trade_date,
                order_book_ids=symbols,
                limit=50000,
            )
        except DataQueryError:
            return {symbol: {"can_buy": True, "can_sell": True} for symbol in symbols}
        output: dict[str, dict[str, bool]] = {}
        for row in frame.to_dict(orient="records"):
            symbol = str(row.get("order_book_id"))
            can_buy = bool(row.get("can_buy", not row.get("is_suspended", False)))
            can_sell = bool(row.get("can_sell", not row.get("is_suspended", False)))
            output[symbol] = {"can_buy": can_buy, "can_sell": can_sell}
        for symbol in symbols:
            output.setdefault(symbol, {"can_buy": True, "can_sell": True})
        return output

    def _latest_positions(self, paper_id: str, before_or_on: str) -> dict[str, int]:
        frame = self.store.read_csv(paper_id, "positions.csv")
        if frame.empty:
            return {}
        frame = frame[frame["trade_date"].astype(str) <= before_or_on]
        if frame.empty:
            return {}
        latest_date = str(frame["trade_date"].max())
        latest = frame[frame["trade_date"].astype(str) == latest_date]
        return {
            str(row.order_book_id): int(row.quantity)
            for row in latest.itertuples()
            if int(row.quantity) != 0
        }

    def _latest_cash(self, paper_id: str, default: float) -> float:
        frame = self.store.read_csv(paper_id, "daily_account.csv")
        if frame.empty:
            return float(default)
        return float(frame.sort_values("trade_date").iloc[-1]["cash"])

    def _target_positions(self, total_value: float, target_weights: dict[str, float], prices: dict[str, float]) -> dict[str, int]:
        targets: dict[str, int] = {}
        for symbol, weight in target_weights.items():
            price = prices[symbol]
            shares = math.floor((total_value * weight / price) / self.lot_size) * self.lot_size
            if shares > 0:
                targets[symbol] = int(shares)
        return targets

    def _rebalance(
        self,
        *,
        trade_date: str,
        cash: float,
        current_positions: dict[str, int],
        target_positions: dict[str, int],
        prices: dict[str, float],
        tradable: dict[str, dict[str, bool]],
    ) -> tuple[float, dict[str, int], list[dict[str, Any]], list[dict[str, Any]]]:
        positions = dict(current_positions)
        orders: list[dict[str, Any]] = []
        trades: list[dict[str, Any]] = []
        symbols = sorted(set(current_positions) | set(target_positions))
        for symbol in symbols:
            current = positions.get(symbol, 0)
            target = target_positions.get(symbol, 0)
            diff = target - current
            if diff == 0:
                continue
            side = "buy" if diff > 0 else "sell"
            flag = tradable.get(symbol, {"can_buy": True, "can_sell": True})
            allowed = flag["can_buy"] if side == "buy" else flag["can_sell"]
            price = prices[symbol]
            requested_quantity = abs(diff)
            filled = requested_quantity if allowed else 0
            reason = ""
            if side == "buy" and filled:
                affordable = math.floor((cash / (price * (1.0 + self.cost_rate))) / self.lot_size) * self.lot_size
                if affordable < filled:
                    filled = max(0, int(affordable))
                    reason = "downsized_for_cash"
            if not allowed:
                reason = "not_tradable"
            status = "filled" if filled == requested_quantity and filled > 0 else ("partial" if filled > 0 else "rejected")
            orders.append(
                {
                    "trade_date": trade_date,
                    "order_book_id": symbol,
                    "side": side,
                    "target_quantity": requested_quantity,
                    "filled_quantity": filled,
                    "price": price,
                    "status": status,
                    "reason": reason,
                }
            )
            if not filled:
                continue
            amount = filled * price
            cost = amount * self.cost_rate
            if side == "buy":
                cash -= amount + cost
                positions[symbol] = positions.get(symbol, 0) + filled
            else:
                cash += amount - cost
                positions[symbol] = positions.get(symbol, 0) - filled
            trades.append(
                {
                    "trade_date": trade_date,
                    "order_book_id": symbol,
                    "side": side,
                    "quantity": filled,
                    "price": price,
                    "amount": amount,
                    "cost": cost,
                }
            )
        positions = {symbol: quantity for symbol, quantity in positions.items() if quantity != 0}
        return cash, positions, orders, trades

    def _position_rows(
        self,
        trade_date: str,
        positions: dict[str, int],
        prices: dict[str, float],
        total_value: float,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for symbol, quantity in sorted(positions.items()):
            market_value = quantity * prices[symbol]
            rows.append(
                {
                    "trade_date": trade_date,
                    "order_book_id": symbol,
                    "quantity": quantity,
                    "close": prices[symbol],
                    "market_value": market_value,
                    "weight": market_value / total_value if total_value else 0.0,
                }
            )
        return rows

    def _replace_trade_date(self, filename: str, paper_id: str, trade_date: str, rows: list[dict[str, Any]]) -> pd.DataFrame:
        frame = self.store.read_csv(paper_id, filename)
        if not frame.empty and "trade_date" in frame.columns:
            frame = frame[frame["trade_date"].astype(str) != trade_date]
        appended = pd.DataFrame(rows)
        if appended.empty:
            output = frame
        elif frame.empty:
            output = appended
        else:
            output = pd.concat([frame, appended], ignore_index=True)
        if not output.empty and "trade_date" in output.columns:
            output = output.sort_values(["trade_date"] + [c for c in ["order_book_id"] if c in output.columns])
        return output.reset_index(drop=True)
