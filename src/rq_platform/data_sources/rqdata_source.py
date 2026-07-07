from __future__ import annotations

from dataclasses import dataclass

import rqdatac

from rq_platform.settings import settings


@dataclass
class RQDataSource:
    initialized: bool = False

    def init(self) -> None:
        if self.initialized:
            return

        if not settings.rqdata_license:
            raise RuntimeError("未找到 RQDATA_LICENSE，请检查项目根目录 .env")

        try:
            # rqdatac 3.5.x does not accept init(license=...) for this license key.
            # The verified license-key login form is username="license" + password=<key>.
            rqdatac.init(username="license", password=settings.rqdata_license)
        except Exception as exc:
            raise RuntimeError(
                f"RQData license 初始化失败：{type(exc).__name__}: {exc}"
            ) from exc

        self.initialized = True

    def info(self):
        self.init()
        return {
            "rqdatac_version": rqdatac.__version__,
            "server": "rqdatad-pro.ricequant.com:16011",
            "initialized": self.initialized,
        }

    def quota(self):
        self.init()
        try:
            return rqdatac.user.get_quota()
        except Exception as exc:
            return {"quota_check_failed": str(exc)}
