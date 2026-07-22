#!/usr/bin/env bash
set -euo pipefail

SERVER_IP="${SERVER_IP:-}"
SERVER_USER="${SERVER_USER:-quant}"
LOCAL_DATA_DIR="${LOCAL_DATA_DIR:-$HOME/Documents/Strategy/quant_platform/data/research_data/rqdata/}"
REMOTE_DATA_DIR="${REMOTE_DATA_DIR:-/opt/quant_platform/data/research_data/rqdata/}"

if [[ -z "$SERVER_IP" ]]; then
  echo "Set SERVER_IP first, for example:"
  echo "  export SERVER_IP=<your_server_ip_or_domain>"
  exit 1
fi

echo "Syncing local Parquet data to server."
echo "Server should read this data locally and should not access RQData by default."
rsync -avz --progress "$LOCAL_DATA_DIR" "${SERVER_USER}@${SERVER_IP}:${REMOTE_DATA_DIR}"
