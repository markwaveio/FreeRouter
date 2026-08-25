# Usage

## Agent or editor

Use these OpenAI-compatible settings:

```text
Base URL: http://127.0.0.1:4000/v1
API Key: <value of LITELLM_MASTER_KEY>
Model: free-router
```

If `FREEROUTER_PORT` differs, replace `4000` with that value. Restart or refresh the Agent after changing its model configuration.

## Choosing a model name

| Name | When to use it |
|---|---|
| `free-router` | Default. Every verified free model, cross-platform failover. |
| `<provider>-free` | Pin to one platform, for example when only that platform is reachable from the current network. |
| `fr/<provider>/<model>` | Pin to one exact model, for reproducing a result or checking a quarantined model by hand. |

`make pool` lists every model with its health and, for failures, the reason. `make changes` shows recent pool changes.

## API request

Read the master key locally without printing it:

```bash
MASTER_KEY=$(sed -n 's/^LITELLM_MASTER_KEY=//p' .env)
curl http://127.0.0.1:4000/v1/chat/completions \
  -H "Authorization: Bearer $MASTER_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"model":"free-router","messages":[{"role":"user","content":"Reply with OK"}],"max_tokens":256}'
```

`make verify` runs the full five-step self-check and prints the exact connection settings a client needs, including the configured port. `make test` sends one request and prints the deployment that answered; `make test zenmux-free` targets one alias.

Give reasoning models room: several free models spend the whole budget on reasoning tokens, so a small `max_tokens` returns HTTP 200 with empty content and non-zero usage. That is the model behaving normally, not a routing failure.

## Inspecting traffic

`make calls` prints recent requests: the alias asked for, the deployment that answered, latency and tokens. The 来源 column separates the application's traffic from the refresher's health probes, which carry the `freerouter-probe` tag. Add `--no-probe` to hide probes.

The Dashboard's Logs page at `/ui` shows the full messages, response and retry chain; the same data is in `GET /spend/logs` and the `LiteLLM_SpendLogs` table.

## Model identity

The completion body shows the public alias. The `x-litellm-model-id` response header carries FreeRouter's deployment id, which starts with `fr-`. Map it through the authenticated `/model/info` endpoint, where `model_info.freerouter_provider` names the platform.

For database-level verification, filter `LiteLLM_SpendLogs` by `model_group='free-router'`. Confirm `status='success'`, non-zero `total_tokens`, the underlying `model`, and `spend=0`.

## Dashboard

Open `http://127.0.0.1:4000/ui`. Use it to manage LiteLLM virtual keys, inspect models, view activity and spend, and configure budgets. FreeRouter itself has no separate UI.

Deployments listed there with an `fr-` id are owned by the refresher. Editing or deleting them by hand is undone on the next cycle; change `providers/*.yaml` instead.

## Change notifications

Set `FREEROUTER_NOTIFY_WEBHOOK` in `.env` to receive added, removed, quarantined, revived, provider-error, and offer-expiry events. Feishu, WeCom, DingTalk, Slack, and Discord payload shapes are detected from the URL; anything else receives `{"text": "..."}`.
