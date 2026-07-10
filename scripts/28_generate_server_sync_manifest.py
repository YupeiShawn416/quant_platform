from __future__ import annotations

import argparse

from rq_platform.etl.server_sync_manifest import write_server_sync_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate server sync manifest.")
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--server-target", default="/opt/quant_platform/data/research_data/rqdata/")
    parser.add_argument("--output-dir", default="reports/generated")
    args = parser.parse_args()

    path = write_server_sync_manifest(
        output_dir=args.output_dir,
        local_data_root=args.data_root,
        server_target=args.server_target,
    )
    print(f"manifest={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
