# VIX Beta Q5 Reconciliation Summary

## Scope

- Pilot project: `/Users/yupeishen/Desktop/vix_beta_q5_long_only_pilot`
- Audit directory: `/Users/yupeishen/Desktop/vix_beta_q5_long_only_pilot/reports/audit`
- Original project: `/Users/yupeishen/Desktop/rq_vix_beta_cross_section`
- Original script: `/Users/yupeishen/Desktop/rq_vix_beta_cross_section/experiments/02_vix_beta_cross_section/scripts/08_backtest_vix_beta_portfolios.py`
- Platform project: `/Users/yupeishen/Desktop/quant_platform`
- Scope: Q5LongOnly only. Q5MinusQ1 and ScoreLongShort are not audited here.

## Scripts Run

```text
python scripts/08_reconcile_with_legacy.py
python scripts/09_audit_platform_result.py --result-zip /tmp/backtest_result_vix_beta_q5_long_only_pilot.zip
python scripts/10_check_timing_and_lookahead.py
python scripts/11_build_audit_report.py
```

## Reconciliation Results

- Dates checked: `243`
- Average holdings: `60.00`
- Average overlap ratio: `1.000000`
- Exact-match date ratio: `1.000000`
- Suspicious dates: `0`
- Max daily weight sum: `1.000000`
- Negative weights: `0`
- Duplicate keys: `0`

Conclusion: the pilot weights match an independent reproduction of the legacy
Q5LongOnly target-weight logic for all checked 2025 dates.

## Platform Result Audit

- total_return: `0.4095660855105021`
- annual_return: `0.4297035561737874`
- sharpe: `2.838860546964993`
- max_drawdown: `-0.07184777633541162`
- trade_count: `3360`
- NAV daily return outliers above 20% absolute return: `0`
- Negative quantity rows: `0`
- Negative price rows: `0`
- Single-name position weight above 10%: `0`
- Max single-name position weight: `0.016679`

No obvious platform result integrity issue was found from NAV, trades, or
positions diagnostics.

## Timing And Lookahead Risk

The current attractive performance should not be treated as a final strategy
validity conclusion. The audit cannot fully rule out future-function or timing
risk because the pilot uses same-date scores as same-date platform weights.

Key risk:

- If `score_negative_vix_beta` is only known after the close on day t, then
  same-date execution is optimistic.
- The legacy script default mode is `same_day_close_to_close`, and it also
  supports a stricter `next_close` mode.
- The next required credibility check is a lagged-weight or next-close
  comparison.

## Recommendation

Treat this as a successful engineering and logic-migration pilot, not a final
investment conclusion.

Next steps:

1. Build a t+1 / lagged weights package and compare platform results.
2. Compare against the legacy `next_close` mode.
3. Compare platform NAV and legacy NAV to attribute residual differences.
4. Extend reconciliation to 2020-2026.
5. Review CSI300 membership and tradability inputs for survivorship or timing bias.
6. Add ScoreLongOnly later.
7. Keep long-short variants out of scope until the platform supports short books.
