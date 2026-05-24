# Loan Default Risk Platform

End-to-end MLOps platform for credit-default risk prediction, with model training, real-time + batch serving, monitoring, drift-triggered retraining, and an LLM/RAG explanation layer.

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the full plan and JD-bullet mapping.

## Status

- [x] Phase 0 — Repo scaffold
- [ ] Phase 1 — Core ML pipeline (DVC + MLflow + fairness + SHAP)
- [ ] Phase 2 — FastAPI serving + Docker
- [ ] Phase 3 — CI/CD (GitHub Actions + Jenkins)
- [ ] Phase 4 — Kubernetes (Helm)
- [ ] Phase 5 — Terraform AWS infra
- [ ] Phase 6 — Monitoring (Prometheus + Grafana + Evidently)
- [ ] Phase 7 — Retraining orchestration (Airflow)
- [ ] Phase 8 — LLM/RAG explanation layer
- [ ] Phase 9 — Polish + resume artifacts

## Quickstart (will fill in as phases complete)

```bash
# create env and install deps
make setup

# pull data, run pipeline
make data
make train

# serve locally
make serve
```

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
