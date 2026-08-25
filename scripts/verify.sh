#!/bin/sh
# 一条命令验证 FreeRouter 是否真的在工作。只读，不会改动任何东西。
# 用法: ./scripts/verify.sh [模型名]   默认 free-router
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
MASTER_KEY=$(sed -n 's/^LITELLM_MASTER_KEY=//p' "$PROJECT_DIR/.env")
PORT=$(sed -n 's/^FREEROUTER_PORT=//p' "$PROJECT_DIR/.env")
PORT=${PORT:-4000}
BASE="http://127.0.0.1:$PORT"
MODEL=${1:-free-router}
STATUS=0

printf '客户端应填的连接信息\n'
printf '  Base URL : %s/v1\n' "$BASE"
printf '  API Key  : .env 里的 LITELLM_MASTER_KEY\n'
printf '  Model    : %s\n\n' "$MODEL"

printf '1/5 网关健康 ....... '
curl -fsS --max-time 10 -o /dev/null "$BASE/health/liveliness" && printf 'OK\n'

printf '2/5 可用模型名 ..... '
curl -fsS --max-time 20 -H "Authorization: Bearer $MASTER_KEY" "$BASE/v1/models" \
  | python3 -c '
import json
import sys

ids = sorted(m["id"] for m in json.load(sys.stdin)["data"])
groups = [i for i in ids if not i.startswith("fr/")]
direct = len(ids) - len(groups)
print("聚合别名 " + ", ".join(groups) + " + " + str(direct) + " 个 fr/... 直连名")
'

printf '3/5 模型池健康度 ... '
python3 - "$PROJECT_DIR/state/health.json" <<'HEALTH_PY'
import collections
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    print("state/health.json 不存在：refresher 还没跑完第一轮")
    raise SystemExit(0)

models = json.loads(path.read_text(encoding="utf-8"))["models"]
tally = collections.Counter(entry["status"] for entry in models.values())
by_provider = collections.Counter(entry["provider"] for entry in models.values())
print(
    "healthy={h} unknown={u} quarantined={q}  平台: {p}".format(
        h=tally["healthy"],
        u=tally["unknown"],
        q=tally["quarantined"],
        p=", ".join(sorted(by_provider)),
    )
)
for key, entry in sorted(models.items()):
    if entry["status"] == "quarantined":
        print("      隔离中 " + key + "  " + str(entry["last_outcome"]))
HEALTH_PY

printf '4/5 刷新器在运行 ... '
if docker compose -f "$PROJECT_DIR/docker-compose.yml" ps --status running --services 2>/dev/null | grep -q refresher; then
  printf 'OK（%s 秒刷新一轮）\n' "$(sed -n 's/^FREEROUTER_REFRESH_INTERVAL=//p' "$PROJECT_DIR/.env")"
else
  printf '未运行，执行 make up\n'
  STATUS=1
fi

printf '5/5 真实请求 ....... '
HEADERS=$(mktemp)
BODY=$(mktemp)
PAYLOAD="{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly OK\"}],\"max_tokens\":256}"
CODE=000
ATTEMPT=1

# 免费模型偶发限流是常态而不是故障，失败重试一次再下结论
while [ "$ATTEMPT" -le 2 ]; do
  CODE=$(curl -sS --max-time 180 -o "$BODY" -D "$HEADERS" -w '%{http_code}' \
    "$BASE/v1/chat/completions" \
    -H "Authorization: Bearer $MASTER_KEY" \
    -H 'Content-Type: application/json' \
    -d "$PAYLOAD" 2>/dev/null) || CODE=000
  [ "$CODE" = "200" ] && break
  ATTEMPT=$((ATTEMPT + 1))
done

if [ "$CODE" = "200" ]; then
  python3 - "$HEADERS" "$BODY" <<'RESULT_PY'
import json
import sys
from pathlib import Path

headers = {}
for line in Path(sys.argv[1]).read_text(errors="replace").splitlines():
    name, sep, value = line.partition(": ")
    if sep:
        headers[name.lower()] = value.strip()

payload = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
usage = payload.get("usage", {})
print(
    "HTTP 200  tokens={t}  命中 {d}".format(
        t=usage.get("total_tokens", 0),
        d=headers.get("x-litellm-model-id", "?"),
    )
)
RESULT_PY
elif [ "$CODE" = "429" ]; then
  printf 'HTTP 429 限流（重试 2 次都被限）\n'
  printf '      免费模型挤爆是常态，网关本身没问题。稍后再试，或指定别的平台：\n'
  printf '      make verify MODEL=zenmux-free\n'
else
  printf 'HTTP %s 失败\n' "$CODE"
  printf '      响应: %s\n' "$(head -c 300 "$BODY" | tr -d '\n')"
  STATUS=1
fi
rm -f "$HEADERS" "$BODY"

printf '\n'
if [ "$STATUS" -eq 0 ]; then
  printf '通过。看变更记录: make changes ｜ 看完整模型池: make pool\n'
else
  printf '有失败项，先看 make logs\n'
fi
exit "$STATUS"
