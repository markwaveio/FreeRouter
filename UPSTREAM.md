# LiteLLM upstream

FreeRouter is a thin routing and configuration layer built on the official LiteLLM Proxy. It does not vendor or fork LiteLLM source code.

- Source: https://github.com/BerriAI/litellm
- Documentation: https://docs.litellm.ai/
- Releases: https://github.com/BerriAI/litellm/releases
- Official Docker image used by default: `docker.litellm.ai/berriai/litellm-database:latest`

## Update LiteLLM

Run:

```bash
make update
```

This pulls the image named by `LITELLM_IMAGE` and recreates the gateway container. Database data stays in the Docker volume, so the free-model pool, virtual keys and spend history survive. The `freerouter-refresher` container reconciles the pool on its next cycle; `make refresh` forces one immediately.

To pin a known LiteLLM version, change `LITELLM_IMAGE` in `.env`. To return to current upstream releases, restore the default image shown above and run `make update`.

FreeRouter keeps its own Git history because it is an integration layer rather than a source fork. The upstream repository remains linked here and in the main README so updates and release notes are always directly accessible.
