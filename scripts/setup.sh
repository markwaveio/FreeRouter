#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ENV_FILE="$PROJECT_DIR/.env"
EXAMPLE_FILE="$PROJECT_DIR/.env.example"

mkdir -p "$PROJECT_DIR/state"

if [ -f "$ENV_FILE" ]; then
  ADDED=0
  while IFS= read -r line; do
    case "$line" in
      ''|'#'*) continue ;;
    esac
    KEY=${line%%=*}
    if ! grep -q "^$KEY=" "$ENV_FILE"; then
      if [ "$ADDED" -eq 0 ]; then
        printf '\n# ── 由 make setup 补充的新配置项 ──\n' >> "$ENV_FILE"
        ADDED=1
      fi
      printf '%s\n' "$line" >> "$ENV_FILE"
      printf '%s\n' "added $KEY"
    fi
  done < "$EXAMPLE_FILE"

  if [ "$ADDED" -eq 0 ]; then
    printf '%s\n' "FreeRouter is already initialized: $ENV_FILE"
  else
    printf '%s\n' "Added new keys to $ENV_FILE; existing values were not touched."
  fi
  exit 0
fi

MASTER_KEY="sk-fr-$(openssl rand -hex 24)"
SALT_KEY="sk-fr-salt-$(openssl rand -hex 24)"
DB_PASSWORD=$(openssl rand -hex 24)

sed \
  -e "s/CHANGE_ME_MASTER_KEY/$MASTER_KEY/" \
  -e "s/CHANGE_ME_SALT_KEY/$SALT_KEY/" \
  -e "s/CHANGE_ME_DB_PASSWORD/$DB_PASSWORD/" \
  "$EXAMPLE_FILE" > "$ENV_FILE"
chmod 600 "$ENV_FILE"

printf '%s\n' "Created $ENV_FILE"
printf '%s\n' "填入任意一个平台的 API Key，然后运行: make up"
