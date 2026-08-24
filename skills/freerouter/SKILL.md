---
name: freerouter
description: Install, configure, operate, update, or troubleshoot the FreeRouter local LiteLLM gateway. Use when the user mentions FreeRouter, free-router, zenmux-free, openrouter-free, or connecting an Agent to a unified free-model API.
---

# FreeRouter

FreeRouter is a thin integration layer over the official [LiteLLM](https://github.com/BerriAI/litellm) Proxy. Preserve that upstream relationship: update the official Docker image rather than copying or modifying LiteLLM source inside this project.

## Route the request

- For a new installation or migration, read [references/install.md](references/install.md).
- For provider keys, aliases, ports, or custom LiteLLM models, read [references/configuration.md](references/configuration.md).
- For Agent, SDK, API, Dashboard, model identity, or spend-log usage, read [references/usage.md](references/usage.md).
- For LiteLLM or FreeRouter updates and version pinning, read [references/update.md](references/update.md).
- For failed startup, provider errors, port conflicts, or missing models, read [references/troubleshooting.md](references/troubleshooting.md).

## Operational invariants

- Never print, commit, paste, or copy a real `.env` value into tracked files or command output.
- Keep `.env` ignored and keep the API bound to `127.0.0.1` unless the user explicitly requests a secured remote deployment.
- Do not classify a ZenMux model as free unless every prompt and completion price rule is zero.
- Treat `free-router`, `zenmux-free`, and `openrouter-free` as generated aliases; custom models must use other names.
- Ask before deleting Docker volumes because they contain Dashboard and usage data.
- Creating repositories, publishing changes, or modifying external systems still requires the user's authorization.

## Completion check

For installation or configuration work, finish only after `docker compose config --quiet`, a healthy gateway, `/v1/models` showing the expected alias, and one authenticated completion returning HTTP 200 with non-zero token usage. Report the selected alias, underlying deployment when available, and recorded spend without exposing keys.
