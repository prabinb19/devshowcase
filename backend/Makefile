.PHONY: dev test

dev:
	uvicorn app.main:app --reload --reload-exclude .venv

test:
	.venv/bin/python -m pytest tests/ -v
