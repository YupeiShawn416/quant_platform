#!/usr/bin/env bash
set -euo pipefail

API_URL="${QUANT_PLATFORM_API_URL:-}"
API_TOKEN="${QUANT_PLATFORM_API_TOKEN:-}"

if [[ -z "$API_URL" ]]; then
  echo "Set QUANT_PLATFORM_API_URL first, for example:"
  echo "  export QUANT_PLATFORM_API_URL=http://SERVER_IP"
  exit 1
fi

if [[ -z "$API_TOKEN" ]]; then
  echo "QUANT_PLATFORM_API_TOKEN is empty. This is only acceptable for local API_TOKEN=change_me."
fi

HEADER_ARGS=()
if [[ -n "$API_TOKEN" ]]; then
  HEADER_ARGS=(-H "X-API-Token: ${API_TOKEN}")
fi

echo "Checking /health"
curl -fsS "${API_URL%/}/health"
echo

echo "Checking /status"
curl -fsS "${HEADER_ARGS[@]}" "${API_URL%/}/status"
echo

echo "Checking small /prices query"
curl -fsS "${HEADER_ARGS[@]}" \
  "${API_URL%/}/prices?symbols=000001.XSHE,600519.XSHG&start=2025-01-02&end=2025-01-10&adjust_type=pre&fields=open,close,volume"
echo
