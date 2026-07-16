import json

import pandas as pd

from factor_pool.__main__ import main
from factor_pool.catalog.builder import REQUIRED_COLUMNS


def test_catalog_validate_cli_returns_safe_summary(tmp_path, capsys):
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    row = {column: None for column in REQUIRED_COLUMNS}
    row.update({
        "snapshot_id": "test",
        "vendor_field_name": "revenue",
        "vendor_category": "income_statement",
        "field_role": "statement_field",
        "classification_status": "source_only",
        "classification_reason": "test",
        "classification_rule_id": "test",
    })
    pd.DataFrame([row]).to_parquet(snapshot / "source_fields.parquet", index=False)
    (snapshot / "request_manifest.json").write_text(
        json.dumps({"snapshot_id": "test", "field_count": 1, "status": "matched"}),
        encoding="utf-8",
    )

    exit_code = main(["catalog", "validate", "--snapshot", str(snapshot)])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output == {"field_count": 1, "snapshot_id": "test", "status": "matched"}


def test_phase_a_run_cli_marks_missing_live_audits_incomplete(tmp_path, capsys):
    source_path = tmp_path / "source_fields.parquet"
    pd.DataFrame([
        {"vendor_field_name": "revenue", "vendor_category": "income_statement", "field_role": "statement_field", "classification_status": "source_only"},
        {"vendor_field_name": "pe_ratio_ttm", "vendor_category": "eod_indicator", "field_role": "vendor_factor", "classification_status": "candidate_factor"},
        {"vendor_field_name": "old_ttm1_0", "vendor_category": "other", "field_role": "unclassified", "classification_status": "quarantined"},
    ]).to_parquet(source_path, index=False)

    exit_code = main([
        "phase-a", "run",
        "--source-catalog", str(source_path),
        "--output-root", str(tmp_path / "runs"),
        "--manifest-root", str(tmp_path / "manifests"),
        "--snapshot-id", "cli-phase-a",
    ])

    assert exit_code == 4
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "incomplete"
    assert output["snapshot_id"] == "cli-phase-a"
