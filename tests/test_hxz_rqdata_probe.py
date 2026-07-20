import os
import subprocess
import sys


def test_hxz_probe_without_key_does_not_require_rqdatac(tmp_path):
    env = os.environ.copy()
    env.pop("RQDATAC_KEY", None)
    env["PYTHONPATH"] = "src"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/47_probe_rqdata_hxz_fields.py",
            "--output-dir",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 2
    assert "No RQData call was made" in result.stdout
    assert (tmp_path / "rqdata_hxz_probe.md").exists()
