# Researcher Token Management

Stage 28 uses one API token per researcher. The token only identifies who
submitted a request. All researcher tokens have the same platform permissions.

## Config Files

Example file:

```text
config/researcher_tokens.example.json
```

Real local file:

```text
config/researcher_tokens.json
```

Do not commit the real file.

## Create Token

```bash
PYTHONPATH=src python scripts/33_manage_researcher_tokens.py create \
  --researcher-id r001 \
  --name "Researcher One"
```

The plaintext token is printed once. Send it to the researcher through a secure
channel.

## List Tokens

```bash
PYTHONPATH=src python scripts/33_manage_researcher_tokens.py list
```

This does not print plaintext tokens.

## Disable Or Enable

```bash
PYTHONPATH=src python scripts/33_manage_researcher_tokens.py disable --researcher-id r001
PYTHONPATH=src python scripts/33_manage_researcher_tokens.py enable --researcher-id r001
```

Disabled tokens return 403.

## Runs And Usage

Runs API:

```text
GET /backtests/runs?researcher_id=r001
GET /backtests/runs?researcher_name=Researcher
```

Dashboard:

```text
/ui/backtests/runs
/ui/researchers
```

Each submitted backtest records researcher id, name, client IP, and user agent.
