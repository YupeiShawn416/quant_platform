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


settings = Settings()
