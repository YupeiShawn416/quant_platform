from pathlib import Path

from factor_pool.config import load_catalog_config


def test_load_catalog_config_resolves_roles_and_output_root():
    config = load_catalog_config(Path("configs/factor_pool/catalog.yaml"))

    assert config.rule_version == "1.0.0"
    assert config.category_roles["income_statement"] == ("statement_field", "source_only")
    assert config.category_roles["eod_indicator"] == ("vendor_factor", "candidate_factor")
    assert config.category_roles["other"] == ("unclassified", "quarantined")
    assert config.output_root.name == "catalog"

