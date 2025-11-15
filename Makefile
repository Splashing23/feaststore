.PHONY: help install dev up down seed apply materialize serve test test-int lint fmt typecheck

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install the package
	pip install .

dev: ## Install with dev extras
	pip install -e ".[dev]"

up: ## Start postgres + redis
	docker compose up -d postgres redis

down: ## Stop all containers
	docker compose down

seed: ## Load synthetic data for the fraud example
	python examples/fraud/seed_data.py

apply: ## Register the fraud example feature views
	feaststore apply examples/fraud/feature_repo.py

materialize: ## Push latest features online
	feaststore materialize

serve: ## Run the serving API locally
	uvicorn feaststore.serving.api:app --reload --port 8000

test: ## Run unit tests (no external services)
	pytest -m "not integration"

test-int: ## Run integration tests (needs docker)
	pytest -m integration

lint: ## Lint
	ruff check feaststore tests

fmt: ## Auto-format
	ruff format feaststore tests
	ruff check --fix feaststore tests

typecheck: ## Type check
	mypy feaststore
