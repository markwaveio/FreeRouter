#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_DIR"

docker compose pull litellm
docker compose up -d --force-recreate litellm
docker compose ps
