# Updates

## Update LiteLLM

FreeRouter uses the image specified by `LITELLM_IMAGE`. Update the upstream proxy with:

```bash
make update
```

This pulls the official image, recreates only the gateway, and refreshes the free-model catalog. It does not delete the Postgres volume.

Before a production update, read the [LiteLLM releases](https://github.com/BerriAI/litellm/releases). To pin a version, set the exact official image tag in `.env`, then run `make update`.

## Update FreeRouter and the Skill

```bash
git pull --ff-only
make check
make update
```

When installed through `make install-skill`, the Skill is symlinked into the repository and therefore updates with the same pull.

## Upstream relationship

FreeRouter does not contain LiteLLM source and is not intended to merge LiteLLM Git history. Keep the official source link at https://github.com/BerriAI/litellm in the README and `UPSTREAM.md`, and update through the official image rather than copying upstream files.
