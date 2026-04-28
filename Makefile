# ─────────────────────────────────────────────────────────────
#  Makefile — Helper commands for AI Backend project
#  Usage:  make <target>
# ─────────────────────────────────────────────────────────────

.PHONY: help up down build logs shell migrate makemigration import-users \
        test lint worker flower clean reset

# Default target — show help
help:
	@echo ""
	@echo "  AI Backend — Available Commands"
	@echo "  ─────────────────────────────────────"
	@echo "  make up              Start all services"
	@echo "  make down            Stop all services"
	@echo "  make build           Rebuild Docker images"
	@echo "  make logs            Tail logs from all services"
	@echo "  make logs-api        Tail API logs only"
	@echo "  make logs-worker     Tail Celery worker logs"
	@echo "  make shell           Open bash shell in API container"
	@echo "  make migrate         Run Alembic migrations"
	@echo "  make makemigration   Create a new migration (MSG=...)"
	@echo "  make import-users    Import fake_users.csv into DB"
	@echo "  make test            Run test suite"
	@echo "  make flower          Open Flower dashboard in browser"
	@echo "  make clean           Remove containers + volumes"
	@echo "  make reset           Full clean + rebuild + migrate"
	@echo ""

# ── Docker Lifecycle ───────────────────────────────────────
up:
	docker compose up -d
	@echo "✅  Services started. API → http://localhost:8000/docs"

down:
	docker compose down

build:
	docker compose build --no-cache

logs:
	docker compose logs -f

logs-api:
	docker compose logs -f api

logs-worker:
	docker compose logs -f worker

# ── Shell Access ───────────────────────────────────────────
shell:
	docker compose exec api bash

shell-db:
	docker compose exec db psql -U aiuser -d aibackend

# ── Database Migrations ────────────────────────────────────
# Run all pending migrations inside the running API container
migrate:
	docker compose exec api alembic upgrade head
	@echo "✅  Migrations applied"

# Create a new migration file.  Usage: make makemigration MSG="add users table"
makemigration:
	docker compose exec api alembic revision --autogenerate -m "$(MSG)"

# Show current migration status
migration-status:
	docker compose exec api alembic current

# Downgrade one step
downgrade:
	docker compose exec api alembic downgrade -1

# ── Data Loading ───────────────────────────────────────────
import-users:
	docker compose exec api python scripts/import_users.py
	@echo "✅  Fake users imported"

# ── Monitoring ─────────────────────────────────────────────
flower:
	@echo "Opening Flower at http://localhost:5555"
	xdg-open http://localhost:5555 || open http://localhost:5555 || true

# Watch active Celery tasks in terminal
watch-tasks:
	docker compose exec api celery -A app.workers.celery_app inspect active

# ── Testing ────────────────────────────────────────────────
test:
	docker compose exec api pytest tests/ -v

# ── Cleanup ────────────────────────────────────────────────
clean:
	docker compose down -v --remove-orphans
	@echo "✅  Containers and volumes removed"

reset: clean build up
	@sleep 5
	$(MAKE) migrate
	$(MAKE) import-users
	@echo "✅  Full reset complete"
