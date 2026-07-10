# Backtest Run Registry

Stage 24 adds a lightweight run registry so every submitted backtest has an
independent `run_id`.

## Why

Before Stage 24, the platform only had `current`. A new submission overwrote the
Dashboard result shown to the previous researcher.

Now:

- `current` still shows the latest result for compatibility.
- every run is recorded in the registry.
- every run can be opened by `run_id` while its cached result files are available.

## Current Vs Runs

```text
current
  latest result only
  old API and Dashboard compatibility

runs/<run_id>
  independent result view
  researcher should save this link
```

## Storage

Registry metadata:

```text
runs/backtests/registry/backtest_runs.jsonl
```

Cached result files:

```text
runs/backtests/cache/<run_id>/
```

Current result:

```text
runs/backtests/current/
```

The registry keeps lightweight metadata. The cache keeps complete result bundle
files for a limited time.

## Expiration

Each registry record has `expires_at`, `result_available`, and `result_expired`.
Cleanup can delete cached files after expiry, but the registry metadata remains.

If cache files are gone, `/backtests/runs/{run_id}` still returns metadata, while
summary/nav/trades/download return a clear unavailable-result error.

## API

List runs:

```text
GET /backtests/runs
```

Run metadata:

```text
GET /backtests/runs/{run_id}
```

Run result files:

```text
GET /backtests/runs/{run_id}/summary
GET /backtests/runs/{run_id}/nav
GET /backtests/runs/{run_id}/trades
GET /backtests/runs/{run_id}/positions
GET /backtests/runs/{run_id}/orders
GET /backtests/runs/{run_id}/logs
GET /backtests/runs/{run_id}/download
```

Cleanup:

```text
POST /backtests/runs/cleanup
```

## Dashboard

Run list:

```text
/ui/backtests/runs
```

Run detail:

```text
/ui/backtests/runs/{run_id}
```

Current remains available:

```text
/ui/backtests/current
```

## Researcher Rule

After submission, save:

- `run_id`
- `/ui/backtests/runs/{run_id}`
- result zip

`current` may still be overwritten by the next submission.
