# Loan Default Risk Platform

[![ci](https://github.com/jayaram9196/mlops-credit-default-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/jayaram9196/mlops-credit-default-platform/actions/workflows/ci.yml)
[![build-deploy](https://github.com/jayaram9196/mlops-credit-default-platform/actions/workflows/build-deploy.yml/badge.svg)](https://github.com/jayaram9196/mlops-credit-default-platform/actions/workflows/build-deploy.yml)
[![python](https://img.shields.io/badge/python-3.11-blue)](pyproject.toml)
[![license](https://img.shields.io/badge/license-MIT-green)](pyproject.toml)

End-to-end MLOps platform for credit-default risk prediction, with model training, real-time + batch serving, monitoring, drift-triggered retraining, and an LLM/RAG explanation layer.

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the full plan and JD-bullet mapping.

## Status

- [x] Phase 0 — Repo scaffold
- [x] Phase 1 — Core ML pipeline (DVC + MLflow + fairness + SHAP)
- [x] Phase 2 — FastAPI serving + Docker
- [x] Phase 3 — CI/CD (GitHub Actions + Jenkins)
- [ ] Phase 4 — Kubernetes (Helm)
- [ ] Phase 5 — Terraform AWS infra
- [ ] Phase 6 — Monitoring (Prometheus + Grafana + Evidently)
- [ ] Phase 7 — Retraining orchestration (Airflow)
- [ ] Phase 8 — LLM/RAG explanation layer
- [ ] Phase 9 — Polish + resume artifacts

## Quickstart

```bash
# 1) create the venv with all deps
python -m venv .venv
.venv/Scripts/activate          # Windows; use `source .venv/bin/activate` on *nix
pip install -e ".[serving,monitoring,dev]"

# 2) run the Phase 1 pipeline (downloads UCI Taiwan default dataset via OpenML)
python -m src.data.ingest
python -m src.data.validate
python -m src.features.build
python -m src.models.train       # ~1 min with optuna_trials=5
python -m src.models.evaluate
python -m src.models.register

# 3) serve the model locally
uvicorn src.serving.app:app --reload --port 8000
# OpenAPI docs: http://localhost:8000/docs

# 4) or run the containerised stack
docker compose -f docker/docker-compose.yml up -d api
curl http://localhost:8000/health
```

## CI/CD

| Workflow | Trigger | Purpose |
| --- | --- | --- |
| [`ci.yml`](.github/workflows/ci.yml) | PR + push to `main` | ruff / black / mypy / pytest unit + integration / bandit / trivy fs scan |
| [`train.yml`](.github/workflows/train.yml) | PR touching `params.yaml` / `src/data\|features\|models/**` | Runs `dvc repro` with reduced budget, comments holdout metrics + fairness on the PR |
| [`build-deploy.yml`](.github/workflows/build-deploy.yml) | Push to `main`, version tags | Builds + pushes the API image to `ghcr.io/jayaram9196/mlops-credit-default-platform`, then trivy image scan |
| [`Jenkinsfile`](Jenkinsfile) | Jenkins-driven | Declarative pipeline mirroring CI: lint → unit tests → smoke pipeline → integration tests → docker build/push → trivy |

## Layout

```
src/
  data/         ingestion, validation
  features/     feature engineering
  models/       training, evaluation, registration
  serving/      FastAPI app
  monitoring/   drift + fairness
  llm/          RAG explanation service
pipelines/      DVC + Airflow DAGs
infra/          Terraform modules
k8s/            manifests + Helm chart
.github/        workflows
tests/          unit + integration
docs/           problem statement, architecture, ADRs
docker/         Dockerfiles (api, training, airflow)
data/           DVC-tracked
notebooks/      exploration only (not pipeline)
```
