# Configuration

## Environment

Run `make setup`, then edit the untracked `.env` file. On an existing install `make setup` appends only the keys that are missing and leaves existing values alone.

### Gateway

| Variable | Purpose |
|---|---|
| `LITELLM_IMAGE` | Official LiteLLM Docker image or a pinned upstream tag |
| `FREEROUTER_PORT` | Local host port; defaults to `4000` |
| `LITELLM_MASTER_KEY` | Credential used by Agents, API clients, and the refresher |
| `LITELLM_SALT_KEY` | Stable LiteLLM key-encryption salt |
| `STORE_MODEL_IN_DB` | Must stay `True`; the refresher's hot updates depend on it |
| `POSTGRES_*` | Local Dashboard, usage, and model-pool database settings |

Keep `LITELLM_SALT_KEY` stable after virtual keys exist. Changing it can make encrypted database values unreadable.

### Refresher

| Variable | Default | Purpose |
|---|---|---|
| `FREEROUTER_REFRESH_INTERVAL` | `21600` | Seconds between cycles; clamped to a 300 second minimum |
| `FREEROUTER_RECHECK_HOURS` | `24` | How stale a healthy model may get before it is re-probed |
| `FREEROUTER_FAILURE_THRESHOLD` | `3` | Consecutive failures before quarantine |
| `FREEROUTER_OFFER_WARN_DAYS` | `14` | Lead time on limited-time offer expiry warnings |
| `FREEROUTER_NOTIFY_WEBHOOK` | empty | Feishu, WeCom, DingTalk, Slack, Discord, or generic JSON endpoint |
| `FREEROUTER_PROBE_WORKERS` | `4` | Providers probed concurrently; models within one provider stay sequential |

### Provider keys

One key is enough to run. Every platform whose credential is empty is skipped with an `INFO` log line, not an error. The full list lives in `.env.example`.

## Generated model names

| Name | Behavior |
|---|---|
| `free-router` | Every probe-verified free model, across all platforms |
| `<provider>-free` | Probe-verified models from one platform, for example `groq-free` |
| `fr/<provider>/<model>` | One exact model, kept even while quarantined |

## Add a platform

Create `providers/<id>.yaml`. No code change is needed.

```yaml
id: newplatform
name: New Platform
name_zh: 新平台
status: active            # active | paused | retired | watch
tier: free                # free | trial | offer
region: cn                # cn | global
credential: NEWPLATFORM_API_KEY
extra_credentials: []     # e.g. an account id required by the catalog URL
litellm_prefix: openai    # a native LiteLLM provider prefix, or openai + api_base
api_base: https://api.newplatform.com/v1
docs_url: https://docs.newplatform.com
console_url: https://newplatform.com/keys
free_basis: 官方文档写明 xxx 系列永久免费
free_basis_checked: 2026-08-25
max_models: 15
limits:
  rpm: 30
discovery:
  mode: listing           # priced_catalog | listing | static
  url: https://api.newplatform.com/v1/models
  auth: bearer            # none | bearer | query_key
  items_path: data
  id_path: id
  allow: []
  deny: ["*embed*"]
probe:
  max_per_cycle: 5
```

Then run `make docs` to regenerate the platform table in `README.md` and the key block in `.env.example` — do not hand-edit those blocks, a CI test compares them against the registry. Add the value to your own `.env` and run `make refresh`.

`make keys` lists every platform, which ones are configured, and where to get a key for the rest.

Rules to respect:

- `free_basis` must state the actual evidence and `free_basis_checked` the date it was verified.
- `priced_catalog` needs `prompt_price_path`, `completion_price_path`, and normally `require_text_io: true` plus `deny_output_modalities: [audio, image, video]`.
- `listing` needs either a non-empty `allow` list or `whole_catalog_is_free: true`, and the registry refuses to load without one. Use the flag only when the platform's entire catalog really is on its free tier (Groq, Cerebras). Aggregators that resell paid models through the same endpoint need the allow list.
- `static` lists may be generous. A model that no longer exists is quarantined on its first probe rather than breaking the pool.
- `status: retired` records a dead platform and never routes. `status: watch` tracks an offer's expiry for a platform that has no usable API.
- `referral_url` is optional and always needs `referral_note` stating what both sides receive, plus a `console_url` giving the reader a plain, non-referral way in. The registry refuses to load an undisclosed referral link.
- URLs and `api_base` support `${ENV_VAR}` placeholders; when a variable is missing the provider is skipped rather than misconfigured.

## Change the port

```dotenv
FREEROUTER_PORT=4001
```

The API becomes `http://127.0.0.1:4001/v1` and the Dashboard `http://127.0.0.1:4001/ui`. The refresher reaches the gateway over the Compose network and is unaffected.

## Add your own paid model

Add the provider key to `.env`, then add an entry under `model_list` in `config/litellm-config.yaml`:

```yaml
model_list:
  - model_name: my-provider-model
    litellm_params:
      model: openai/provider/model-id
      api_base: https://provider.example/v1
      api_key: os.environ/MY_PROVIDER_API_KEY
```

Restart after editing:

```bash
docker compose restart litellm
```

The refresher only touches deployments whose `model_info.id` starts with `fr-`, so config-file models are never removed.
