from __future__ import annotations

import duckdb
import pandas as pd


def query(sql: str) -> pd.DataFrame:
    connection = duckdb.connect(database=":memory:")
    try:
        return connection.execute(sql).fetchdf()
    finally:
        connection.close()
