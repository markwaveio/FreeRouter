#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ENV_FILE="$PROJECT_DIR/.env"

if [ -f "$ENV_FILE" ]; then
  printf '%s\n' "FreeRouter is already initialized: $ENV_FILE"
  exit 0
fi

MASTER_KEY="sk-fr-$(openssl rand -hex 24)"
SALT_KEY="sk-fr-salt-$(openssl rand -hex 24)"
DB_PASSWORD=$(openssl rand -hex 24)

sed \
  -e "s/CHANGE_ME_MASTER_KEY/$MASTER_KEY/" \
  -e "s/CHANGE_ME_SALT_KEY/$SALT_KEY/" \
  -e "s/CHANGE_ME_DB_PASSWORD/$DB_PASSWORD/" \
  "$PROJECT_DIR/.env.example" > "$ENV_FILE"
chmod 600 "$ENV_FILE"

printf '%s\n' "Created $ENV_FILE"
printf '%s\n' "Add ZENMUX_API_KEY or OPENROUTER_API_KEY, then run: make up"
