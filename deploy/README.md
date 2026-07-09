# Deployment Templates

This directory contains safe templates for MVP server deployment.

- `systemd/quant-platform-api.service`: FastAPI service template.
- `nginx/quant-platform.conf`: nginx reverse proxy template.
- `scripts/`: optional helper scripts with placeholders only.

Do not commit real server IPs, API tokens, private keys, or `.env` files.

Full runbook:

```text
docs/SERVER_DEPLOYMENT_RUNBOOK_MVP.md
```

Smoke test:

```text
docs/SERVER_DEPLOYMENT_SMOKE_TEST.md
```
