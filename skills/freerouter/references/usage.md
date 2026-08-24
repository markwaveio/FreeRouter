# Usage

## Agent or editor

Use these OpenAI-compatible settings:

```text
Base URL: http://127.0.0.1:4000/v1
API Key: <value of LITELLM_MASTER_KEY>
Model: free-router
```

If `FREEROUTER_PORT` differs, replace `4000` with that value. Restart or refresh the Agent after changing its model configuration.

## API request

Read the master key locally without printing it:

```bash
MASTER_KEY=$(sed -n 's/^LITELLM_MASTER_KEY=//p' .env)
curl http://127.0.0.1:4000/v1/chat/completions \
  -H "Authorization: Bearer $MASTER_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"model":"free-router","messages":[{"role":"user","content":"Reply with OK"}]}'
```

`make test` performs the same kind of authenticated check without displaying the key.

## Model identity

The completion body may show the public alias instead of the underlying deployment. Inspect the `x-litellm-model-id` response header, then map it through the authenticated `/v1/model/info` endpoint. The Dashboard's model and spend views provide the same mapping.

For database-level verification, filter `LiteLLM_SpendLogs` by `model_group='free-router'`. Confirm `status='success'`, non-zero `total_tokens`, the underlying `model`, and `spend=0`.

## Dashboard

Open `http://127.0.0.1:4000/ui`. Use it to manage LiteLLM virtual keys, inspect models, view activity and spend, and configure budgets. FreeRouter itself has no separate UI.
