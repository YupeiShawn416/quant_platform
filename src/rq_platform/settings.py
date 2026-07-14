from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

from rq_platform.paths import PROJECT_ROOT

load_dotenv(PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    rqdata_license: Optional[str] = None

    data_root: str = "./data/research_data/rqdata"
    rqalpha_bundle_path: str = "./data/rqalpha_bundle"

    api_token: str = "change_me"
    researcher_tokens_path: str = "./config/researcher_tokens.json"
    host: str = "127.0.0.1"
    port: int = 8000
    workers: int = 2
    backtest_execution_mode: str = "local"
    backtest_result_ttl_hours: int = 24
    backtest_current_dir: str = "./runs/backtests/current"
    backtest_jobs_dir: str = "./runs/backtests/jobs"
    backtest_run_registry_path: str = "./runs/backtests/registry/backtest_runs.jsonl"
    backtest_run_cache_dir: str = "./runs/backtests/cache"
    data_access_log_path: str = "./runs/data_access/data_access_log.jsonl"
    paper_accounts_dir: str = "./runs/paper_trading/accounts"
    paper_registry_path: str = "./runs/paper_trading/registry/paper_accounts.jsonl"
    factor_library_dir: str = "./data/factor_library"
    factor_weights_dir: str = "./runs/factor_weights"
    backtest_image: str = "quant-platform-backtest:latest"
    backtest_cpu_limit: str = "1.0"
    backtest_memory_limit: str = "2g"
    backtest_timeout_seconds: int = 600

    @property
    def data_root_path(self) -> Path:
        path = Path(self.data_root)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    @property
    def rqalpha_bundle_path_obj(self) -> Path:
        path = Path(self.rqalpha_bundle_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    @property
    def backtest_current_dir_path(self) -> Path:
        path = Path(self.backtest_current_dir)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    @property
    def backtest_jobs_dir_path(self) -> Path:
        path = Path(self.backtest_jobs_dir)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    @property
    def backtest_run_registry_path_obj(self) -> Path:
        path = Path(self.backtest_run_registry_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    @property
    def backtest_run_cache_dir_path(self) -> Path:
        path = Path(self.backtest_run_cache_dir)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    @property
    def researcher_tokens_path_obj(self) -> Path:
        path = Path(self.researcher_tokens_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    @property
    def data_access_log_path_obj(self) -> Path:
        path = Path(self.data_access_log_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    @property
    def paper_accounts_dir_path(self) -> Path:
        path = Path(self.paper_accounts_dir)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    @property
    def paper_registry_path_obj(self) -> Path:
        path = Path(self.paper_registry_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    @property
    def factor_library_dir_path(self) -> Path:
        path = Path(self.factor_library_dir)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    @property
    def factor_weights_dir_path(self) -> Path:
        path = Path(self.factor_weights_dir)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()


settings = Settings()
