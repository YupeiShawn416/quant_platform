from __future__ import annotations

from pathlib import Path

from rq_platform.research.vix_q5_audit import (
    compute_exposure_summary,
    load_pilot_weights,
    render_exposure_markdown,
)


OUTPUT_PATH = Path("docs/VIX_Q5_EXPOSURE_AUDIT.md")


def main() -> None:
    weights = load_pilot_weights()
    summary = compute_exposure_summary(weights)
    OUTPUT_PATH.write_text(render_exposure_markdown(summary), encoding="utf-8")

    print("VIX Q5 exposure audit complete")
    print(f"date range: {summary['date_range'][0]} to {summary['date_range'][1]}")
    print(f"unique symbols: {summary['unique_symbols']}")
    print(f"average holdings: {summary['average_holdings']:.2f}")
    print(f"index overlap: {summary['index_overlap_average_weight']}")
    print(f"report: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
