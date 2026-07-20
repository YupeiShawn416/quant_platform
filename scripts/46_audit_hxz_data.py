from __future__ import annotations

import argparse

from rq_platform.etl.hxz_data_audit import build_hxz_audit, write_hxz_audit_outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit local data lake readiness for China HXZ replication.")
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--output-dir", default="reports/data_audit")
    parser.add_argument("--manifest-dir", default=None)
    args = parser.parse_args()

    audit = build_hxz_audit(data_root=args.data_root)
    outputs = write_hxz_audit_outputs(
        audit,
        output_dir=args.output_dir,
        manifest_dir=args.manifest_dir,
    )
    print(f"data_root={audit['data_root']}")
    print(f"ready_for_full_hxz_replication={audit['local_readiness']['ready_for_full_hxz_replication']}")
    print(f"missing_hxz_requirements={audit['local_readiness']['missing_count']}")
    print(f"partial_or_derivable_requirements={audit['local_readiness']['partial_or_derivable_count']}")
    for name, path in outputs.items():
        print(f"{name}={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
