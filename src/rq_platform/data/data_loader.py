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

DEFAULT_TRADABILITY_FIELDS = [
    "trade_date",
    "order_book_id",
    "is_listed",
    "is_suspended",
    "is_st",
    "can_buy",
    "can_sell",
    "reason",
]

DEFAULT_VALUATION_FIELDS = [
    "trade_date",
    "order_book_id",
    "market_cap",
    "float_market_cap",
    "pe_ratio",
    "pb_ratio",
    "ps_ratio",
    "pcf_ratio",
    "turnover_rate",
]

DEFAULT_INDUSTRY_FIELDS = [
    "trade_date",
    "order_book_id",
    "industry_system",
    "industry_level",
    "industry_code",
    "industry_name",
]

DEFAULT_INDEX_COMPONENT_FIELDS = ["trade_date", "index_id", "order_book_id"]
DEFAULT_INDEX_WEIGHT_FIELDS = ["trade_date", "index_id", "order_book_id", "weight"]


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

    def load_tradability(
        self,
        symbols: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        start = start_date or "1900-01-01"
        end = end_date or "2999-12-31"
        paths = self._tradability_paths(start, end)
        existing_paths = [path for path in paths if path.exists()]
        if not existing_paths:
            return pd.DataFrame(columns=DEFAULT_TRADABILITY_FIELDS)

        files_sql = ", ".join(_quote_string(str(path)) for path in existing_paths)
        where_clauses = [
            f"trade_date BETWEEN {_quote_string(start)} AND {_quote_string(end)}"
        ]
        if symbols:
            symbols_sql = ", ".join(_quote_string(symbol) for symbol in symbols)
            where_clauses.append(f"order_book_id IN ({symbols_sql})")
        where_sql = " AND ".join(where_clauses)
        select_sql = ", ".join(_quote_identifier(column) for column in DEFAULT_TRADABILITY_FIELDS)
        sql = f"""
            SELECT {select_sql}
            FROM read_parquet([{files_sql}], union_by_name=true)
            WHERE {where_sql}
            ORDER BY trade_date, order_book_id
        """
        try:
            return query(sql)
        except duckdb.BinderException:
            return pd.DataFrame(columns=DEFAULT_TRADABILITY_FIELDS)

    def _tradability_paths(self, start: str, end: str) -> list[Path]:
        root = dataset_dir("tradability_1d")
        return [root / f"year={year}.parquet" for year in _years_between(start, end)]

    def load_valuation(
        self,
        symbols: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        fields: list[str] | None = None,
    ) -> pd.DataFrame:
        start = start_date or "1900-01-01"
        end = end_date or "2999-12-31"
        paths = self._valuation_paths(start, end)
        existing_paths = [path for path in paths if path.exists()]
        selected_fields = DEFAULT_VALUATION_FIELDS if fields is None else [
            "trade_date",
            "order_book_id",
            *fields,
        ]
        if not existing_paths:
            return pd.DataFrame(columns=selected_fields)

        files_sql = ", ".join(_quote_string(str(path)) for path in existing_paths)
        where_clauses = [
            f"trade_date BETWEEN {_quote_string(start)} AND {_quote_string(end)}"
        ]
        if symbols:
            symbols_sql = ", ".join(_quote_string(symbol) for symbol in symbols)
            where_clauses.append(f"order_book_id IN ({symbols_sql})")
        where_sql = " AND ".join(where_clauses)
        select_sql = ", ".join(_quote_identifier(column) for column in selected_fields)
        sql = f"""
            SELECT {select_sql}
            FROM read_parquet([{files_sql}], union_by_name=true)
            WHERE {where_sql}
            ORDER BY trade_date, order_book_id
        """
        try:
            return query(sql)
        except duckdb.BinderException:
            return pd.DataFrame(columns=selected_fields)

    def _valuation_paths(self, start: str, end: str) -> list[Path]:
        root = dataset_dir("valuation_1d")
        return [root / f"year={year}.parquet" for year in _years_between(start, end)]

    def load_industry(
        self,
        symbols: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        industry_system: str | None = None,
    ) -> pd.DataFrame:
        start = start_date or "1900-01-01"
        end = end_date or "2999-12-31"
        return self._load_dataset(
            dataset_name="industry_classification",
            paths=self._industry_paths(start, end),
            selected_fields=DEFAULT_INDUSTRY_FIELDS,
            start=start,
            end=end,
            symbol_column="order_book_id",
            symbols=symbols,
            extra_filters={"industry_system": industry_system} if industry_system else None,
            order_by="trade_date, order_book_id",
        )

    def load_index_components(
        self,
        index_ids: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        start = start_date or "1900-01-01"
        end = end_date or "2999-12-31"
        return self._load_dataset(
            dataset_name="index_components",
            paths=self._index_component_paths(start, end),
            selected_fields=DEFAULT_INDEX_COMPONENT_FIELDS,
            start=start,
            end=end,
            symbol_column="index_id",
            symbols=index_ids,
            order_by="trade_date, index_id, order_book_id",
        )

    def load_index_weights(
        self,
        index_ids: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        start = start_date or "1900-01-01"
        end = end_date or "2999-12-31"
        return self._load_dataset(
            dataset_name="index_weights",
            paths=self._index_weight_paths(start, end),
            selected_fields=DEFAULT_INDEX_WEIGHT_FIELDS,
            start=start,
            end=end,
            symbol_column="index_id",
            symbols=index_ids,
            order_by="trade_date, index_id, order_book_id",
        )

    def _industry_paths(self, start: str, end: str) -> list[Path]:
        root = dataset_dir("industry_classification")
        return [root / f"year={year}.parquet" for year in _years_between(start, end)]

    def _index_component_paths(self, start: str, end: str) -> list[Path]:
        root = dataset_dir("index_components")
        return [root / f"year={year}.parquet" for year in _years_between(start, end)]

    def _index_weight_paths(self, start: str, end: str) -> list[Path]:
        root = dataset_dir("index_weights")
        return [root / f"year={year}.parquet" for year in _years_between(start, end)]

    def _load_dataset(
        self,
        dataset_name: str,
        paths: list[Path],
        selected_fields: list[str],
        start: str,
        end: str,
        symbol_column: str,
        symbols: list[str] | None,
        order_by: str,
        extra_filters: dict[str, str] | None = None,
    ) -> pd.DataFrame:
        existing_paths = [path for path in paths if path.exists()]
        if not existing_paths:
            return pd.DataFrame(columns=selected_fields)
        files_sql = ", ".join(_quote_string(str(path)) for path in existing_paths)
        where_clauses = [f"trade_date BETWEEN {_quote_string(start)} AND {_quote_string(end)}"]
        if symbols:
            symbols_sql = ", ".join(_quote_string(symbol) for symbol in symbols)
            where_clauses.append(f"{_quote_identifier(symbol_column)} IN ({symbols_sql})")
        for column, value in (extra_filters or {}).items():
            where_clauses.append(f"{_quote_identifier(column)} = {_quote_string(value)}")
        where_sql = " AND ".join(where_clauses)
        select_sql = ", ".join(_quote_identifier(column) for column in selected_fields)
        sql = f"""
            SELECT {select_sql}
            FROM read_parquet([{files_sql}], union_by_name=true)
            WHERE {where_sql}
            ORDER BY {order_by}
        """
        try:
            return query(sql)
        except duckdb.BinderException:
            return pd.DataFrame(columns=selected_fields)


def _years_between(start: str, end: str) -> list[int]:
    start_year = date.fromisoformat(start).year
    end_year = date.fromisoformat(end).year
    return list(range(start_year, end_year + 1))


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _quote_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
