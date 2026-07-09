# Server Deployment Runbook MVP

## 1. Deployment Goal

This runbook deploys the 2025 data MVP. The goal is to let one server provide:

- Data API
- Dashboard
- unified backtest judge
- Strategy Package upload and execution
- result zip download

The server is not the place where every researcher runs every research script.
Researchers can work locally, in notebooks, or in AI-agent projects. The server
accepts the final standard `strategy_package.zip` and produces the platform
backtest result.

The server defaults to a local Parquet copy and should not directly access
RQData unless authorization, IP policy, and license scope are confirmed.

## 2. Recommended Server

MVP recommendation:

- x86_64
- Ubuntu 22.04 LTS
- 4 vCPU
- 16GB RAM
- at least 80GB disk
- lightweight cloud is acceptable for trial
- long-term production should use ECS + independent data disk

## 3. Directory Layout

Recommended layout:

```text
/opt/quant_platform
/opt/quant_platform/.venv
/opt/quant_platform/.env
/opt/quant_platform/data/research_data/rqdata
/opt/quant_platform/runs/backtests/current
/opt/quant_platform/runs/backtests/jobs
```

## 4. Server Bootstrap

Example commands. Replace package names if your image differs.

```bash
sudo apt update
sudo apt install -y git curl wget rsync nginx python3.11 python3.11-venv python3-pip build-essential unzip htop docker.io
```

Create a deployment user:

```bash
sudo adduser quant
sudo usermod -aG sudo quant
sudo usermod -aG docker quant
```

Log out and back in after adding the user to `docker`.

## 5. Clone And Install

```bash
cd /opt
sudo git clone <PRIVATE_REPO_URL> quant_platform
sudo chown -R quant:quant /opt/quant_platform
cd /opt/quant_platform
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

## 6. Environment Config

```bash
cp .env.production.example .env
nano .env
```

Do not commit `.env`. Do not send API tokens in chat groups.

Generate a token:

```bash
python - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
```

Important production values:

```text
HOST=127.0.0.1
PORT=8000
WORKERS=2
API_TOKEN=<strong_random_token>
DATA_ROOT=/opt/quant_platform/data/research_data/rqdata
BACKTEST_EXECUTION_MODE=docker
BACKTEST_CURRENT_DIR=/opt/quant_platform/runs/backtests/current
BACKTEST_JOBS_DIR=/opt/quant_platform/runs/backtests/jobs
```

`BACKTEST_EXECUTION_MODE=local` may be used only for a trusted MVP trial. It is
not recommended for untrusted strategy code.

## 7. Sync Data

Run from the authorized local machine that already has Parquet data:

```bash
rsync -avz --progress \
  ~/Desktop/quant_platform/data/research_data/rqdata/ \
  quant@SERVER_IP:/opt/quant_platform/data/research_data/rqdata/
```

The server should read the copied Parquet data. It should not directly access
RQData by default.

## 8. Build Docker Image

The repository contains:

```text
docker/backtest.Dockerfile
```

Build command:

```bash
docker build -f docker/backtest.Dockerfile -t quant-platform-backtest:latest .
```

Current status: Docker runner command construction exists and production config
points to `BACKTEST_EXECUTION_MODE=docker`, but the Docker image is still a
template and needs server-side validation before running untrusted code.

If Docker is not ready, a trusted MVP trial can use local execution, but do not
use local execution for untrusted uploaded strategies.

## 9. Install systemd Service

```bash
sudo cp deploy/systemd/quant-platform-api.service /etc/systemd/system/quant-platform-api.service
sudo systemctl daemon-reload
sudo systemctl enable quant-platform-api
sudo systemctl start quant-platform-api
sudo systemctl status quant-platform-api --no-pager
```

Logs:

```bash
journalctl -u quant-platform-api -f
```

## 10. Install Nginx

Edit `deploy/nginx/quant-platform.conf` and replace `<SERVER_NAME>` with a
domain or `_` for an IP-only trial.

```bash
sudo cp deploy/nginx/quant-platform.conf /etc/nginx/sites-available/quant-platform
sudo ln -s /etc/nginx/sites-available/quant-platform /etc/nginx/sites-enabled/quant-platform
sudo nginx -t
sudo systemctl reload nginx
```

Use HTTPS for any non-private deployment.

## 11. Security Group

- 22 only from administrator IPs
- 80/443 open
- 8000 not open to the public

Nginx should be the public entry point. Uvicorn should bind to `127.0.0.1`.

## 12. Smoke Test

Use:

```text
docs/SERVER_DEPLOYMENT_SMOKE_TEST.md
```

## 13. Update Code Later

```bash
cd /opt/quant_platform
git pull
source .venv/bin/activate
python -m pip install -e .
sudo systemctl restart quant-platform-api
sudo systemctl status quant-platform-api --no-pager
```

## 14. Update Data Later

Run the same `rsync` command from the authorized local machine after local ETL
and quality checks pass.

## 15. What Not To Do

- Do not access RQData at scale from the server unless authorization is confirmed.
- Do not expose port 8000 to the public internet.
- Do not commit `.env`.
- Do not permanently pile up `runs/` without cleanup.
- Do not run all researcher scripts on the server.
- Do not turn the platform API into an external data service.
- Do not paste tokens, server IPs, or private keys into committed docs.
