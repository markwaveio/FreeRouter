# Troubleshooting

## Start with evidence

```bash
docker compose config --quiet
docker compose ps
docker compose logs --tail=200 litellm
```

Do not include `.env` values in copied logs or issue reports.

## No provider configured

If startup says to set `ZENMUX_API_KEY` or `OPENROUTER_API_KEY`, add at least one real key to `.env` and recreate the gateway:

```bash
docker compose up -d --force-recreate litellm
```

## No zero-price ZenMux models

FreeRouter fails closed when ZenMux returns no qualifying models. Check whether the catalog is reachable and whether the current pricing still contains zero-price prompt and completion rules. Do not weaken the filter to price preference or a name suffix.

## Port already in use

Change `FREEROUTER_PORT` in `.env`, then recreate the service. Keep the host binding on `127.0.0.1` unless a secured remote deployment was explicitly requested.

## Database or Dashboard errors

Confirm `freerouter-db` is healthy before diagnosing the gateway. Preserve `LITELLM_SALT_KEY` and the Postgres password after first use. Do not run `docker compose down -v` unless the user explicitly authorizes deletion of local keys, spend logs, and Dashboard data.

## Provider succeeds directly but alias fails

Inspect `/v1/model/info` for the alias deployments and compare the upstream model slug with the provider catalog. Restart the gateway to regenerate the pool. Use `x-litellm-model-id` and `LiteLLM_SpendLogs` to identify the exact selected deployment.
