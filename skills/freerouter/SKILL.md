---
name: freerouter
description: Install, configure, operate, update, or troubleshoot the FreeRouter local LiteLLM gateway and its self-healing free-model pool. Use when the user mentions FreeRouter, free-router, a `<platform>-free` alias, `fr/…` model names, the refresher container, providers/*.yaml, or connecting an Agent to a unified free-model API.
---

# FreeRouter

FreeRouter is a thin integration layer over the official [LiteLLM](https://github.com/BerriAI/litellm) Proxy. Preserve that upstream relationship: update the official Docker image rather than copying or modifying LiteLLM source inside this project.

## Architecture in one pass

Three containers: `freerouter-db` (Postgres), `freerouter-gateway` (stock LiteLLM), `freerouter-refresher` (this project's Python package).

The gateway serves only what is in `config/litellm-config.yaml` plus what the refresher writes into LiteLLM's database. The refresher is the **single writer** of the free-model pool:

1. reads `providers/*.yaml`, skipping any platform whose credential is absent;
2. discovers candidate models (`priced_catalog` / `listing` / `static`);
3. registers new models under `fr/<provider>/<model>` only;
4. reads LiteLLM's call log and folds real request outcomes into the same health state, so traffic replaces synthetic probes;
5. probes only what traffic cannot cover — never-verified models, quarantined models on backoff, and healthy models that have gone quiet;
6. promotes passing models into `free-router` and `<provider>-free`, quarantines failures;
7. reconciles via `POST /model/new` and `POST /model/delete`, never restarting the gateway;
8. writes `state/health.json`, appends `state/changelog.jsonl`, posts to the webhook.

## Route the request

- For a new installation or migration, read [references/install.md](references/install.md).
- For provider keys, adding a platform, refresh tuning, or custom LiteLLM models, read [references/configuration.md](references/configuration.md).
- For Agent, SDK, API, Dashboard, model identity, or spend-log usage, read [references/usage.md](references/usage.md).
- For LiteLLM or FreeRouter updates and version pinning, read [references/update.md](references/update.md).
- For failed startup, provider errors, quarantined models, port conflicts, or an empty pool, read [references/troubleshooting.md](references/troubleshooting.md).

## Operational invariants

- Never print, commit, paste, or copy a real `.env` value into tracked files or command output.
- Keep `.env` ignored and keep the API bound to `127.0.0.1` unless the user explicitly requests a secured remote deployment.
- Do not weaken a `free_basis` rule to grow the pool. Price-preference, a name suffix, or "it looks free" are not evidence. A `priced_catalog` model needs every prompt and completion rate at zero **and** no audio, image, or video output modality.
- A `listing` provider must justify itself: either a non-empty `allow` list, or `whole_catalog_is_free: true`. Never set that flag to silence the loader — an aggregator that resells GPT or Claude through the same `/models` endpoint needs the allow list. The registry refuses to load otherwise.
- `free-router`, `<provider>-free`, and `fr/<provider>/<model>` are generated names owned by the refresher. Custom models must use other names and live in `config/litellm-config.yaml`.
- Deployments whose `model_info.id` starts with `fr-` belong to FreeRouter. Never hand-edit or delete them through the Dashboard; change `providers/*.yaml` and run `make refresh`.
- A referral link never earns a platform inclusion, a higher `max_models`, or a place ahead of another. Selection is `free_basis` plus probe results; ordering is alphabetical by provider id. `discovery`, `planning`, `probe`, `refresh` and `traffic` must not reference the referral fields at all, and a test enforces it.
- Probing spends the user's free quota, so it is the last resort, not the default. Prefer the call log. Never raise a `probe.max_per_cycle` past 25% of a platform's published daily quota; a CI test enforces this.
- A discovery error must not empty the pool. If a platform's catalog is unreachable, the previous models stay until a probe actually fails.
- Adding a platform means adding `providers/<id>.yaml` plus its env var in `.env.example`. It must not require code changes.
- Ask before deleting Docker volumes because they contain the model pool, Dashboard and usage data.
- Creating repositories, publishing changes, or modifying external systems still requires the user's authorization.

## Completion check

For installation or configuration work, finish only after `make check` passes and `make verify` reports all five steps green. Always read `FREEROUTER_PORT` from `.env` before telling the user a URL; it is not always 4000. Report the number of healthy and quarantined models, the selected deployment when available, and recorded spend, without exposing keys.
