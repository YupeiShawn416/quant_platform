from __future__ import annotations

from pathlib import Path

from rq_platform.settings import settings


SYNC_DATASETS = [
    "instruments",
    "trading_calendar",
    "prices_1d_pre",
    "prices_1d_none",
    "index_prices_1d",
    "tradability_1d",
    "valuation_1d",
    "industry_classification",
    "index_components",
    "index_weights",
]


def render_server_sync_manifest(
    local_data_root: str | Path | None = None,
    server_target: str = "/opt/quant_platform/data/research_data/rqdata/",
) -> str:
    local_root = Path(local_data_root).resolve() if local_data_root is not None else settings.data_root_path
    lines = [
        "# Server Sync Manifest",
        "",
        f"Local data root: `{local_root}`",
        f"Server target: `{server_target}`",
        "",
        "## Datasets To Sync",
        "",
    ]
    for dataset in SYNC_DATASETS:
        lines.append(f"- `{dataset}/`")
    lines.extend(
        [
            "",
            "## Recommended rsync",
            "",
            "```bash",
            f"rsync -avz --delete \\",
            f"  --exclude '.env' --exclude 'runs/' --exclude 'logs/' \\",
            f"  {local_root}/ <user>@<server>:{server_target}",
            "```",
            "",
            "## Do Not Sync",
            "",
            "- `.env`",
            "- `runs/`",
            "- logs with sensitive information",
            "- API tokens or license files",
        ]
    )
    return "\n".join(lines) + "\n"


def write_server_sync_manifest(
    output_dir: str | Path = "reports/generated",
    local_data_root: str | Path | None = None,
    server_target: str = "/opt/quant_platform/data/research_data/rqdata/",
) -> Path:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "server_sync_manifest.md"
    path.write_text(
        render_server_sync_manifest(local_data_root, server_target),
        encoding="utf-8",
    )
    return path
