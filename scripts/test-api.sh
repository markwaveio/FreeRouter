#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
MASTER_KEY=$(sed -n 's/^LITELLM_MASTER_KEY=//p' "$PROJECT_DIR/.env")
PORT=${FREEROUTER_PORT:-$(sed -n 's/^FREEROUTER_PORT=//p' "$PROJECT_DIR/.env")}
PORT=${PORT:-4000}

curl -fsS --max-time 120 \
  "http://127.0.0.1:$PORT/v1/chat/completions" \
  -H "Authorization: Bearer $MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"free-router","messages":[{"role":"user","content":"Reply with exactly OK"}],"max_tokens":128}' \
  | python3 -m json.tool
