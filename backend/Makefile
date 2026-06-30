.PHONY: help up down logs shell migrate makemigrations seed test lint fmt psql install bash

help:
	@echo "Targets:"
	@echo "  install           - install Python deps locally (no Docker)"
	@echo "  up                - start the full stack via Docker Compose"
	@echo "  down              - stop the stack"
	@echo "  logs              - follow logs"
	@echo "  shell             - Django shell"
	@echo "  bash              - bash inside web container"
	@echo "  migrate           - run migrations"
	@echo "  makemigrations    - create migrations"
	@echo "  seed              - seed all demo data (auth + demo + platform admin)"
	@echo "  test              - run pytest"
	@echo "  lint              - ruff check"
	@echo "  fmt               - ruff format"
	@echo "  psql              - psql into the db container"

install:
	pip install -r requirements-dev.txt

up:
	docker compose up -d --build
	@echo "Stack up. Web: http://localhost:8000  MailHog: http://localhost:8025"

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

shell:
	docker compose exec web python manage.py shell

bash:
	docker compose exec web bash

migrate:
	docker compose exec web python manage.py migrate

makemigrations:
	docker compose exec web python manage.py makemigrations

seed:
	docker compose exec web python manage.py seed_auth
	docker compose exec web python manage.py create_platform_admin

test:
	docker compose exec web pytest

lint:
	docker compose exec web ruff check .

fmt:
	docker compose exec web ruff format .

psql:
	docker compose exec db psql -U $${POSTGRES_USER:-subpilot} -d $${POSTGRES_DB:-subpilot}
