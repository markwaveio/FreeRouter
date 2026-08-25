# Troubleshooting

## Start with evidence

```bash
docker compose config --quiet
docker compose ps
docker compose logs --tail=200 refresher
docker compose logs --tail=100 litellm
make pool
```

Do not include `.env` values in copied logs or issue reports.

## The pool is empty

Read the refresher log first. `skip <provider>: missing <VAR>` is expected for every platform without a key and is not the problem. Then check, in order:

1. Did a cycle finish? Look for `cycle complete: discovered=… healthy=…`.
2. Is at least one platform's credential present in `.env`?
3. Did the gateway become healthy? The refresher waits for it and logs a warning if it did not.

Force a cycle with `make refresh`.

## A model is quarantined

`make pool` prints the recorded reason. The outcome determines the recovery:

| Reason in the log | Meaning | What to do |
|---|---|---|
| `missing` | The platform removed the model | Nothing. If it came from a `static` list, delete it from `providers/<id>.yaml`. |
| `exhausted` | Free quota is spent | Nothing. It is re-probed within the hour, and daily quotas reset. |
| `auth` | The key is rejected | Check the key and whether the platform requires real-name verification or service activation. |
| `transient` | Timeouts or 5xx | Nothing. Three consecutive failures are required, then exponential backoff up to 12 hours. |

Rate limiting (`throttled`) never counts as a failure, so a busy model stays in the pool.

To retest one model immediately, call it directly through its `fr/<provider>/<model>` name.

Once the underlying cause is fixed, do not wait out the backoff: `make recheck` clears quarantine and failure counts so the next cycle re-probes, and `make recheck P=<provider>` limits that to one platform.

## A platform returns HTTP 200 with no content

Some platforms need a non-standard parameter. ModelScope's reasoning models return `"choices": null` for non-streaming calls unless `enable_thinking: false` is sent. Put such a parameter in the provider's `extra_params`, which merges into every deployment's `litellm_params` so probes and real traffic both carry it. Never fix this in the probe alone — a model that passes verification but returns nothing to users is worse than one that fails openly.

## A whole provider reports an error

The changelog records one `provider_error` per distinct message, not one per cycle. A catalog outage does **not** empty that platform's models; they stay until a probe actually fails. Verify the catalog URL by hand, then check whether the platform changed its response shape and update the `items_path` / `id_path` fields in `providers/<id>.yaml`.

## No models pass the free-model rules

FreeRouter fails closed rather than routing a paid model. Check whether the platform still publishes zero-price entries, or whether an `allow`/`deny` rule is now too tight. Do not relax the rule to price preference or a name suffix.

## Port already in use

Change `FREEROUTER_PORT` in `.env`, then recreate the service. Keep the host binding on `127.0.0.1` unless a secured remote deployment was explicitly requested. The refresher talks to the gateway over the Compose network and needs no change.

## Hot updates are not applied

`/model/new` and `/model/delete` require `STORE_MODEL_IN_DB=True` and a reachable database. Confirm `freerouter-db` is healthy and that `LITELLM_MASTER_KEY` in the refresher's environment matches the gateway's.

## Database or Dashboard errors

Confirm `freerouter-db` is healthy before diagnosing the gateway. Preserve `LITELLM_SALT_KEY` and the Postgres password after first use. Do not run `docker compose down -v` unless the user explicitly authorizes deletion of the model pool, local keys, spend logs, and Dashboard data.

## Provider succeeds directly but the alias fails

Compare `litellm_params.model` in `/model/info` with the platform's own model id. A wrong `litellm_prefix` is the usual cause: prefer a native LiteLLM provider prefix, or `openai` plus an explicit `api_base`. Use `x-litellm-model-id` and `LiteLLM_SpendLogs` to identify the exact selected deployment.
