def test_imports_and_paths():
    from pathlib import Path

    import rq_platform
    from rq_platform.paths import PROJECT_ROOT
    from rq_platform.settings import settings

    checkout_root = Path(__file__).resolve().parents[1]

    assert Path(rq_platform.__file__).resolve().is_relative_to(checkout_root)
    assert PROJECT_ROOT == checkout_root
    assert (PROJECT_ROOT / "pyproject.toml").is_file()
    assert (PROJECT_ROOT / "src" / "rq_platform").is_dir()
    assert settings.data_root_path.name == "rqdata"
    assert settings.rqalpha_bundle_path_obj.name == "rqalpha_bundle"
