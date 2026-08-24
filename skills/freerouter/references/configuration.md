# Configuration

## Environment

Run `make setup`, then edit the untracked `.env` file.

| Variable | Purpose |
|---|---|
| `LITELLM_IMAGE` | Official LiteLLM Docker image or a pinned upstream tag |
| `FREEROUTER_PORT` | Local host port; defaults to `4000` |
| `LITELLM_MASTER_KEY` | Credential used by Agents and API clients |
| `LITELLM_SALT_KEY` | Stable LiteLLM key-encryption salt |
| `ZENMUX_API_KEY` | Enables dynamically discovered zero-price ZenMux models |
| `OPENROUTER_API_KEY` | Enables OpenRouter's official free router |
| `POSTGRES_*` | Local Dashboard and usage database settings |

Keep `LITELLM_SALT_KEY` stable after virtual keys exist. Changing it can make encrypted database values unreadable.

## Generated aliases

| Alias | Behavior |
|---|---|
| `free-router` | All enabled FreeRouter-managed free deployments |
| `zenmux-free` | ZenMux text models whose prompt and completion price rules are all zero |
| `openrouter-free` | OpenRouter's `openrouter/free` entry |

The startup generator replaces deployments using these three names. Do not use them for custom entries.

## Add a regular LiteLLM model

Add the provider key to `.env`, then add an entry under `model_list` in `config/litellm-config.yaml`:

```yaml
model_list:
  - model_name: my-provider-model
    litellm_params:
      model: openai/provider/model-id
      api_base: https://provider.example/v1
      api_key: os.environ/MY_PROVIDER_API_KEY
```

Use LiteLLM's provider prefix and parameters for native integrations. Restart after editing:

```bash
docker compose restart litellm
```

The generator preserves custom model names and appends the automatic free aliases.

## Change the port

Set, for example:

```dotenv
FREEROUTER_PORT=4001
```

The API then becomes `http://127.0.0.1:4001/v1` and the Dashboard becomes `http://127.0.0.1:4001/ui`.
