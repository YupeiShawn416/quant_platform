import builtins
import importlib
import importlib.util
import sys
from pathlib import Path


def test_status_script_import_does_not_require_rqdatac(monkeypatch):
    _block_rqdatac(monkeypatch)

    path = Path("scripts/32_check_daily_update_status.py").resolve()
    spec = importlib.util.spec_from_file_location("check_daily_update_status_import_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    assert hasattr(module, "main")


def test_read_only_daily_update_modules_do_not_require_rqdatac(monkeypatch):
    _block_rqdatac(monkeypatch)

    for module_name in [
        "rq_platform.etl.daily_update_plan",
        "rq_platform.etl.daily_update_report",
        "rq_platform.etl.daily_update_reconcile",
    ]:
        sys.modules.pop(module_name, None)
        module = importlib.import_module(module_name)
        assert module is not None


def test_daily_update_core_import_does_not_require_rqdatac(monkeypatch):
    _block_rqdatac(monkeypatch)
    sys.modules.pop("rq_platform.etl.daily_update_core", None)

    module = importlib.import_module("rq_platform.etl.daily_update_core")

    assert hasattr(module, "run_daily_update")


def test_daily_update_core_lazy_rqdatac_import_only_for_real_source(monkeypatch):
    _block_rqdatac(monkeypatch)
    sys.modules.pop("rq_platform.etl.daily_update_core", None)
    module = importlib.import_module("rq_platform.etl.daily_update_core")

    try:
        module._new_rqdata_source()
    except ModuleNotFoundError as exc:
        assert exc.name == "rqdatac"
    else:
        raise AssertionError("expected rqdatac import to be lazy and fail only when source is requested")


def _block_rqdatac(monkeypatch):
    original_import = builtins.__import__
    sys.modules.pop("rqdatac", None)
    sys.modules.pop("rq_platform.data_sources.rqdata_source", None)

    def guarded_import(name, *args, **kwargs):
        if name == "rqdatac" or name.startswith("rqdatac."):
            raise ModuleNotFoundError("No module named 'rqdatac'", name="rqdatac")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
