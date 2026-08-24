.PHONY: setup up down logs status test update install-skill check

setup:
	./scripts/setup.sh

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f litellm

status:
	docker compose ps

test:
	./scripts/test-api.sh

update:
	./scripts/update-litellm.sh

install-skill:
	./scripts/install-skill.sh

check:
	uv run pytest
	uv run ruff check .
	uv run basedpyright
	docker compose config --quiet
