.PHONY: setup dev lint typecheck test build check check-api migrate seed cron

PYTHON_BIN := $(shell if [ -x /opt/homebrew/bin/python3.11 ]; then echo /opt/homebrew/bin/python3.11; elif command -v python3.11 >/dev/null 2>&1; then command -v python3.11; else command -v python3; fi)
VENV_DIR := services/api/.venv
API_URL ?= http://localhost:8000/api/v1

setup:
	"$(PYTHON_BIN)" -m venv $(VENV_DIR)
	$(VENV_DIR)/bin/pip install --upgrade pip
	$(VENV_DIR)/bin/pip install -e "services/api[dev]"
	cd apps/web && npm install

dev:
	@bash -c '\
		set -e; \
		trap '''kill 0''' EXIT INT TERM; \
		$(VENV_DIR)/bin/uvicorn app.main:app --app-dir services/api --reload --port 8000 & \
		(cd apps/web && npm run dev -- --port 3000) & \
		wait \
	'

lint:
	$(VENV_DIR)/bin/ruff check services/api infra db/migrations
	$(VENV_DIR)/bin/black --check services/api infra db/migrations
	cd apps/web && npm run lint
	cd apps/web && npm run format:check

typecheck:
	$(VENV_DIR)/bin/mypy services/api/app
	cd apps/web && npm run typecheck

test:
	PYTHONPATH=services/api $(VENV_DIR)/bin/pytest services/api/tests

build:
	cd apps/web && npm run build

check: lint typecheck test build

check-api:
	PYTHONPATH=services/api $(VENV_DIR)/bin/python infra/scripts/smoke_test.py --base-url "$(API_URL)" --health-only

migrate:
	PYTHONPATH=services/api $(VENV_DIR)/bin/alembic -c db/alembic.ini upgrade head

seed:
	PYTHONPATH=services/api $(VENV_DIR)/bin/python infra/scripts/seed.py

cron:
	PYTHONPATH=services/api $(VENV_DIR)/bin/python infra/scripts/daily_job.py
