# Updates

## Update LiteLLM

FreeRouter uses the image specified by `LITELLM_IMAGE`. Update the upstream proxy with:

```bash
make update
```

This pulls the official image and recreates only the gateway. It does not delete the Postgres volume, so the model pool, virtual keys, and spend history survive. The refresher reconciles on its next cycle; run `make refresh` to do it immediately.

Before a production update, read the [LiteLLM releases](https://github.com/BerriAI/litellm/releases). To pin a version, set the exact official image tag in `.env`, then run `make update`.

## Update FreeRouter and the Skill

```bash
git pull --ff-only
make setup     # appends any new .env keys, leaves existing values alone
make check
make up
```

When installed through `make install-skill`, the Skill is symlinked into the repository and therefore updates with the same pull.

## Update the free-model catalog

Two independent mechanisms, neither of which needs a restart:

- **Runtime**: the refresher rediscovers and re-probes every `FREEROUTER_REFRESH_INTERVAL` seconds. `make refresh` forces a cycle.
- **Repository**: `.github/workflows/watch-free-models.yml` runs daily, diffs each platform's public catalog against `catalog/snapshot.json`, and opens a pull request when something changed. `make catalog` does the same locally.

Review such a pull request on two questions: is a newly listed model genuinely free, and does a disappeared model also need removing from a `static` list in `providers/`?

## Upstream relationship

FreeRouter does not contain LiteLLM source and is not intended to merge LiteLLM Git history. Keep the official source link at https://github.com/BerriAI/litellm in the README and `UPSTREAM.md`, and update through the official image rather than copying upstream files.
