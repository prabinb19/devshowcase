.PHONY: up down dev-backend dev-frontend test lint db-migrate help

# Full stack (Docker)
up:
	docker compose up --build

down:
	docker compose down

# Local dev (no Docker for app servers)
dev-backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --reload-exclude .venv

dev-frontend:
	cd frontend && npm run dev

# Database
db-migrate:
	cd backend && .venv/bin/alembic upgrade head

# Quality
test:
	cd backend && .venv/bin/python -m pytest tests/ -v

lint:
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .
	cd frontend && npm run lint

help:
	@echo "make up             - Start full stack with Docker"
	@echo "make down           - Stop all containers"
	@echo "make dev-backend    - Run backend locally (requires .venv)"
	@echo "make dev-frontend   - Run frontend locally (requires node_modules)"
	@echo "make db-migrate     - Run Alembic migrations"
	@echo "make test           - Run backend tests"
	@echo "make lint           - Run ruff + eslint"
