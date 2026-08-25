.PHONY: setup up down logs status test verify calls keys docs recheck update install-skill check refresh pool changes catalog

setup:
	./scripts/setup.sh

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f litellm refresher

status:
	docker compose ps

test:
	./scripts/test-api.sh

verify:
	./scripts/verify.sh $(MODEL)

refresh:
	docker compose exec refresher python -m freerouter refresh

recheck:
	docker compose exec refresher python -m freerouter recheck $(P)
	docker compose exec refresher python -m freerouter refresh

pool:
	docker compose exec refresher python -m freerouter report

changes:
	docker compose exec refresher python -m freerouter changes

calls:
	docker compose exec refresher python -m freerouter calls $(N)

keys:
	uv run python -m freerouter keys

docs:
	uv run python -m freerouter docs

catalog:
	uv run python -m freerouter watch providers
	uv run python -m freerouter docs

update:
	./scripts/update-litellm.sh

install-skill:
	./scripts/install-skill.sh

check:
	uv run pytest
	uv run ruff check .
	uv run basedpyright
	docker compose config --quiet
