.PHONY: install lint format typecheck boundaries test eval audit check up down

install:
	uv sync --all-extras

lint:
	uv run ruff check . && uv run ruff format --check .

format:
	uv run ruff check --fix . && uv run ruff format .

typecheck:
	uv run mypy libs/aibase

boundaries:
	uv run python scripts/check_boundaries.py

test:
	uv run pytest --cov --cov-report=term-missing

eval:
	PYTHONPATH=libs uv run python -m aibase.evals.run evals/datasets

audit:
	uv run pip-audit && uv run bandit -q -r libs services -x '*/tests/*'

check: lint typecheck boundaries test eval

up:
	docker compose up --build

down:
	docker compose down -v
