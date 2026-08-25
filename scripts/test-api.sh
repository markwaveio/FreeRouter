#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
MASTER_KEY=$(sed -n 's/^LITELLM_MASTER_KEY=//p' "$PROJECT_DIR/.env")
PORT=${FREEROUTER_PORT:-$(sed -n 's/^FREEROUTER_PORT=//p' "$PROJECT_DIR/.env")}
PORT=${PORT:-4000}
MODEL=${1:-free-router}
HEADERS=$(mktemp)

curl -fsS --max-time 180 \
  "http://127.0.0.1:$PORT/v1/chat/completions" \
  -H "Authorization: Bearer $MASTER_KEY" \
  -H "Content-Type: application/json" \
  -D "$HEADERS" \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly OK\"}],\"max_tokens\":256}" \
  | python3 -m json.tool

printf '\n实际命中的 deployment: %s\n' "$(sed -n 's/^[Xx]-[Ll]ite[Ll][Ll][Mm]-[Mm]odel-[Ii]d: //p' "$HEADERS" | tr -d '\r')"
rm -f "$HEADERS"
