from rq_platform.settings import settings


def test_runtime_settings_defaults():
    assert hasattr(settings, "host")
    assert hasattr(settings, "port")
    assert hasattr(settings, "workers")
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert isinstance(settings.port, int)
    assert isinstance(settings.workers, int)
