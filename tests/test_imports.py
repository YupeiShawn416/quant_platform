def test_imports_and_paths():
    import rq_platform
    from rq_platform.paths import PROJECT_ROOT
    from rq_platform.settings import settings

    assert rq_platform is not None
    assert PROJECT_ROOT.name == "quant_platform"
    assert settings.data_root_path.name == "rqdata"
    assert settings.rqalpha_bundle_path_obj.name == "rqalpha_bundle"
