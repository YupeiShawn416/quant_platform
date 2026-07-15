# Day-End Operations

This runbook describes the daily after-market workflow. It is deliberately
batch-based: the platform is not a realtime trading system.

## Schedule

Recommended schedule in China time:

```text
16:30 local authorized Mac: daily ETL dry-run, real update, quality checks
16:45 local authorized Mac: rsync verified Parquet data to server
17:00 server/API: run all active paper accounts for the latest complete trade date
```

Use the latest complete trading day only. Do not use a date before the market
has closed and the local data lake has passed quality checks.

## Local Data Update

Run on the authorized local machine that can access RQData:

```bash
cd /Users/yupeishen/Desktop/quant_platform
conda activate quant_platform

make daily-update-dry-run END_DATE=<latest_complete_trade_date>
make daily-update END_DATE=<latest_complete_trade_date>
make daily-update-status
make daily-update-report
make audit-data-lake
make check-data-2016-present
make reconcile-daily-update
make server-sync-manifest
```

Only rsync when quality issues are zero and reconciliation recommends rsync.
Use the administrator-approved rsync command from the generated manifest.

## Paper Trading Daily Run

After server data has been synced and the API is healthy, run:

```bash
export QUANT_PLATFORM_API_URL="http://39.106.218.30"
export QUANT_PLATFORM_API_TOKEN="<server_or_researcher_token>"

make paper-run-daily-all TRADE_DATE=<latest_complete_trade_date>
```

This calls:

```text
POST /paper/run-daily-all
```

It runs each active paper account independently. One failed account should not
prevent the endpoint from returning results for other accounts.

## Automation

Use cron, launchd, or another local scheduler to run the local update workflow
around 16:30-17:00. Keep credentials outside Git.

Example cron shape:

```text
30 16 * * 1-5 cd /Users/yupeishen/Desktop/quant_platform && /bin/zsh -lc 'source ~/.quant_platform_private_env && make daily-update-dry-run END_DATE=$(date +\%F) && make daily-update END_DATE=$(date +\%F) && make audit-data-lake && make check-data-2016-present && make reconcile-daily-update && make server-sync-manifest'
00 17 * * 1-5 cd /Users/yupeishen/Desktop/quant_platform && /bin/zsh -lc 'source ~/.quant_platform_private_env && make paper-run-daily-all TRADE_DATE=$(date +\%F)'
```

The private env file can hold `QUANT_PLATFORM_API_URL`,
`QUANT_PLATFORM_API_TOKEN`, and any local shell aliases needed for rsync. Do not
commit that file. Add the rsync command only after the reconciliation step has
proven stable in daily operation.

## Dynamic Weight Strategies

Paper trading currently consumes `target_weights.csv`; it does not run live
strategy code inside the server.

For a strategy with dynamic weights, the current production-safe workflow is:

```text
daily data update
  -> researcher/agent computes target_weights.csv for the next paper date
  -> upload target_weights.csv to the paper account
  -> run paper-run-daily-all for that trade date
```

This keeps strategy code outside the server and lets the platform remain the
execution and accounting layer. A future enhancement can add a scheduled
"strategy weight generator" service, but that should be treated as a separate
product step with sandboxing, logs, and failure isolation.

## Checks

After the run, open:

```text
http://39.106.218.30/ui/data
http://39.106.218.30/ui/paper
```

Confirm active accounts have advanced to the latest complete trade date.

## Do Not Commit

Do not commit:

```text
.env
config/researcher_tokens.json
data/
runs/
*.parquet
*.zip
reports/generated/
reports/backfill_snapshots/
```
