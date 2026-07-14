from __future__ import annotations

from rq_platform.settings import settings


STATUS_PATH = settings.data_root_path / "update_logs" / "daily_update_status.csv"
STATUS_COLUMNS = [
    "run_id",
    "created_at",
    "dataset",
    "start_date",
    "end_date",
    "year",
    "status",
    "row_count",
    "output_files",
    "error",
]
