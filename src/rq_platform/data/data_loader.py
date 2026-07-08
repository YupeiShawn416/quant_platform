from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

from rq_platform.data.duckdb_query import query
from rq_platform.data.parquet_lake import dataset_dir


DEFAULT_PRICE_FIELDS = [
    "trade_date",
    "order_book_id",
    "adjust_type",
    "open",
    "high",
    "low",
    "close",
    "volume",
]

DEFAULT_INDEX_PRICE_FIELDS = [
    "trade_date",
    "order_book_id",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "total_turnover",
    "num_trades",
]


class ResearchDataLoader:
    def load_prices(
        self,
        symbols: list[str],
        start: str,
        end: str,
        adjust_type: str = "pre",
        fields: list[str] | None = None,
    ) -> pd.DataFrame:
        paths = self._price_paths(adjust_type, start, end)
        existing_paths = [path for path in paths if path.exists()]
        if not existing_paths:
            return pd.DataFrame(columns=DEFAULT_PRICE_FIELDS)

        selected_fields = DEFAULT_PRICE_FIELDS if fields is None else [
            "trade_date",
            "order_book_id",
            "adjust_type",
            *fields,
        ]
        select_sql = ", ".join(_quote_identifier(column) for column in selected_fields)
        files_sql = ", ".join(_quote_string(str(path)) for path in existing_paths)
        symbols_sql = ", ".join(_quote_string(symbol) for symbol in symbols)
        sql = f"""
            SELECT {select_sql}
            FROM read_parquet([{files_sql}], union_by_name=true)
            WHERE order_book_id IN ({symbols_sql})
              AND adjust_type = {_quote_string(adjust_type)}
              AND trade_date BETWEEN {_quote_string(start)} AND {_quote_string(end)}
            ORDER BY order_book_id, trade_date
        """
        try:
            return query(sql)
        except duckdb.BinderException:
            fallback_fields = [
                column
                for column in selected_fields
                if column in {"trade_date", "order_book_id", "adjust_type"}
            ]
            return pd.DataFrame(columns=fallback_fields)

    def _price_paths(self, adjust_type: str, start: str, end: str) -> list[Path]:
        root = dataset_dir(f"prices_1d_{adjust_type}")
        return [root / f"year={year}.parquet" for year in _years_between(start, end)]

    def load_index_prices(
        self,
        index_ids: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        start = start_date or "1900-01-01"
        end = end_date or "2999-12-31"
        paths = self._index_price_paths(start, end)
        existing_paths = [path for path in paths if path.exists()]
        if not existing_paths:
            return pd.DataFrame(columns=DEFAULT_INDEX_PRICE_FIELDS)

        files_sql = ", ".join(_quote_string(str(path)) for path in existing_paths)
        where_clauses = [
            f"trade_date BETWEEN {_quote_string(start)} AND {_quote_string(end)}"
        ]
        if index_ids:
            ids_sql = ", ".join(_quote_string(index_id) for index_id in index_ids)
            where_clauses.append(f"order_book_id IN ({ids_sql})")
        where_sql = " AND ".join(where_clauses)
        select_sql = ", ".join(_quote_identifier(column) for column in DEFAULT_INDEX_PRICE_FIELDS)
        sql = f"""
            SELECT {select_sql}
            FROM read_parquet([{files_sql}], union_by_name=true)
            WHERE {where_sql}
            ORDER BY order_book_id, trade_date
        """
        try:
            return query(sql)
        except duckdb.BinderException:
            return pd.DataFrame(columns=DEFAULT_INDEX_PRICE_FIELDS)

    def _index_price_paths(self, start: str, end: str) -> list[Path]:
        root = dataset_dir("index_prices_1d")
        return [root / f"year={year}.parquet" for year in _years_between(start, end)]


def _years_between(start: str, end: str) -> list[int]:
    start_year = date.fromisoformat(start).year
    end_year = date.fromisoformat(end).year
    return list(range(start_year, end_year + 1))


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _quote_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
