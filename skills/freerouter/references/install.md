# Installation

## Prerequisites

- Docker Desktop or Docker Engine with Compose v2
- Git
- OpenSSL
- At least one ZenMux or OpenRouter API key

## Install

Choose a user-approved project directory. Do not place FreeRouter inside an unrelated website or application repository.

```bash
git clone https://github.com/markwaveio/FreeRouter.git
cd FreeRouter
make setup
```

`make setup` creates `.env` with random LiteLLM, salt, and database keys. It does not create provider credentials. Ask the user to place at least one of these into `.env` without sending the value through chat:

```dotenv
ZENMUX_API_KEY=
OPENROUTER_API_KEY=
```

Start and verify:

```bash
make up
make status
make test
```

The expected result is a healthy `freerouter-gateway`, an HTTP 200 completion, and non-zero token usage. If the default port is already occupied, read [configuration.md](configuration.md) before starting.

## Install this Skill

From the project root:

```bash
make install-skill
```

The installer creates a symlink at `${CODEX_HOME:-$HOME/.codex}/skills/freerouter`, so Git pulls automatically update the installed Skill. It refuses to overwrite an existing destination.
