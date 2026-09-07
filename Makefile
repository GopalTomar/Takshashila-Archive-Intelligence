.PHONY: help setup dev api web worker test migrate seed acceptance lint docker-up docker-down manifest

help:
	@echo "Takshashila Archive Intelligence — common tasks"
	@echo "  make setup       Create venv, install backend + frontend deps"
	@echo "  make dev         Run API (8000) and web (3000) locally"
	@echo "  make api         Run the FastAPI backend only"
	@echo "  make web         Run the Next.js frontend only"
	@echo "  make migrate     Apply Alembic migrations"
	@echo "  make seed        Seed synthetic DEMO data"
	@echo "  make test        Run the pytest suite"
	@echo "  make acceptance  Run the end-to-end vertical-slice acceptance script"
	@echo "  make manifest    Write archive_manifest.{csv,json}"
	@echo "  make docker-up   docker compose up --build"
	@echo "  make docker-down docker compose down"

VENV=.venv/bin
PYTHONPATH_ENV=PYTHONPATH=apps/api

setup:
	python3 -m venv .venv
	$(VENV)/pip install --upgrade pip
	$(VENV)/pip install -r apps/api/requirements.txt
	cd apps/web && npm install

migrate:
	cd apps/api && $(PYTHONPATH_ENV) ../../$(VENV)/alembic upgrade head

api:
	$(PYTHONPATH_ENV) $(VENV)/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --app-dir apps/api

web:
	cd apps/web && npm run dev

worker:
	$(PYTHONPATH_ENV) $(VENV)/celery -A app.jobs.celery_app.celery_app worker --loglevel=info --workdir apps/api

dev:
	@echo "Run 'make api' and 'make web' in two terminals (or use docker-up)."

test:
	$(PYTHONPATH_ENV) $(VENV)/python -m pytest

acceptance:
	$(PYTHONPATH_ENV) $(VENV)/python scripts/acceptance.py

manifest:
	$(PYTHONPATH_ENV) $(VENV)/python scripts/generate_manifest.py

lint:
	$(VENV)/python -m compileall -q apps/api/app

docker-up:
	docker compose up --build

docker-down:
	docker compose down
