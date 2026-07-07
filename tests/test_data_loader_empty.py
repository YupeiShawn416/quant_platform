from rq_platform.data.data_loader import DEFAULT_PRICE_FIELDS, ResearchDataLoader
from rq_platform.settings import settings


def test_load_prices_returns_empty_frame_when_local_files_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_root", str(tmp_path))

    frame = ResearchDataLoader().load_prices(
        symbols=["000001.XSHE"],
        start="2025-01-02",
        end="2025-01-10",
        adjust_type="pre",
    )

    assert frame.empty
    assert list(frame.columns) == DEFAULT_PRICE_FIELDS
