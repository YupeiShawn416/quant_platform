import pandas as pd

from factor_pool.data_adapter.ingredient_backfill import backfill_ingredient_values


class FakeProvider:
    def values(self, ids, fields, date):
        values = {"a": [1.0, 2.0], "b": [None, 3.0]}
        return pd.DataFrame({field: values[field] for field in fields}, index=ids)


def test_ingredient_backfill_writes_resumable_field_chunks(tmp_path):
    controls = pd.DataFrame({"order_book_id": ["A.X", "B.X"]})
    first = backfill_ingredient_values(
        FakeProvider(), controls=controls, fields=["a", "b"], signal_date="2025-12-31",
        output_root=tmp_path, chunk_size=1,
    )
    second = backfill_ingredient_values(
        FakeProvider(), controls=controls, fields=["a", "b"], signal_date="2025-12-31",
        output_root=tmp_path, chunk_size=1,
    )

    assert first == {"written": 2, "cached": 0, "failed": 0, "cells": 4}
    assert second == {"written": 0, "cached": 2, "failed": 0, "cells": 4}
    files = list((tmp_path / "date=2025-12-31").glob("fields=*.parquet"))
    assert len(files) == 2
