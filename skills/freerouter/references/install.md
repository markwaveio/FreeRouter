# Installation

## Prerequisites

- Docker Desktop or Docker Engine with Compose v2
- Git
- OpenSSL
- At least one platform API key from the list in `.env.example`

## Install

Choose a user-approved project directory. Do not place FreeRouter inside an unrelated website or application repository.

```bash
git clone https://github.com/markwaveio/FreeRouter.git
cd FreeRouter
make setup
```

`make setup` creates `.env` with random LiteLLM, salt, and database keys, and creates `state/`. It does not create provider credentials. Ask the user to place at least one platform key into `.env` without sending the value through chat. Any platform left empty is skipped, not an error.

Start and verify:

```bash
make up        # db, gateway, refresher
make status
make pool      # first cycle usually lands within a minute
make test
```

The expected result is a healthy `freerouter-gateway` and `freerouter-refresher`, a non-empty pool, an HTTP 200 completion, and non-zero token usage. If the default port is already occupied, read [configuration.md](configuration.md) before starting.

## Upgrading an existing install

A pre-0.2 install generated the pool at container start from `freerouter_config.py`. That file is gone; the pool now lives in LiteLLM's database and is maintained by the refresher.

```bash
git pull --ff-only
make setup     # appends the new keys to .env, leaves existing values alone
make up        # recreates the gateway and starts the refresher
make pool
```

The old config-generated deployments disappear when the gateway is recreated. Nothing in the Postgres volume needs to be deleted, and virtual keys and spend history are preserved.

## Install this Skill

From the project root:

```bash
make install-skill
```

The installer creates a symlink at `${CODEX_HOME:-$HOME/.codex}/skills/freerouter`, so Git pulls automatically update the installed Skill. It refuses to overwrite an existing destination.
