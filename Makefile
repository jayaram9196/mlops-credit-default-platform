.PHONY: help setup setup-dev install clean lint format test test-unit test-int data train serve docker-build docker-up docker-down

PYTHON := python
VENV := .venv
ACTIVATE := . $(VENV)/Scripts/activate  # Windows; use $(VENV)/bin/activate on *nix

help:
	@echo "Common targets:"
	@echo "  setup       Create venv and install runtime + serving deps"
	@echo "  setup-dev   Create venv and install everything incl. dev deps"
	@echo "  lint        Run ruff + mypy"
	@echo "  format      Run black + ruff --fix"
	@echo "  test        Run all tests"
	@echo "  data        Pull data via DVC"
	@echo "  train       Run dvc repro pipeline"
	@echo "  serve       Run FastAPI locally"
	@echo "  docker-up   docker compose up the full stack"
	@echo "  docker-down docker compose down"

setup:
	$(PYTHON) -m venv $(VENV)
	$(ACTIVATE) && pip install -U pip && pip install -e ".[serving]"

setup-dev:
	$(PYTHON) -m venv $(VENV)
	$(ACTIVATE) && pip install -U pip && pip install -e ".[serving,llm,monitoring,dev]"
	$(ACTIVATE) && pre-commit install

clean:
	rm -rf $(VENV) build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage

lint:
	ruff check src tests
	mypy src

format:
	black src tests
	ruff check --fix src tests

test:
	pytest

test-unit:
	pytest -m unit

test-int:
	pytest -m integration

data:
	dvc pull

train:
	dvc repro

serve:
	uvicorn src.serving.app:app --reload --host 0.0.0.0 --port 8000

docker-build:
	docker build -f docker/Dockerfile.api -t loan-default-api:latest .

docker-up:
	docker compose -f docker/docker-compose.yml up -d

docker-down:
	docker compose -f docker/docker-compose.yml down
