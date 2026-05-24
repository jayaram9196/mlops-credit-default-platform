# Architecture

## High-level diagram

```
                          ┌────────────────────────────────────────────────┐
                          │              AWS (Terraform-managed)            │
                          │                                                 │
   UCI source   ─▶ S3 raw ─▶ DVC ─▶ S3 processed ─▶ Training jobs          │
                                                              │             │
                                                              ▼             │
                                                MLflow Tracking + Registry │
                                              (Postgres backend, S3 artifacts)
                                                              │             │
                                       ┌──────────────────────┴────────┐    │
                                       ▼                               ▼    │
                              Real-time API (EKS)            Batch (Lambda) │
                              FastAPI + Gunicorn              S3 trigger    │
                                       │                                    │
                                       ▼                                    │
                              Prometheus + Grafana                          │
                              Evidently (drift)                             │
                              CloudWatch                                    │
                                       │                                    │
                                       ▼                                    │
                              Airflow (drift-triggered retrain)             │
                              Step Functions (alt path)                     │
                                       │                                    │
                                       ▼                                    │
                              RAG Explanation Service                       │
                              (LangChain + FAISS / Bedrock)                 │
                          └────────────────────────────────────────────────┘

   CI/CD: GitHub Actions (primary)  +  Jenkinsfile (alternate)
   GitOps: Argo CD (optional)
```

## Component responsibilities

| Component | Tech | Purpose |
| --- | --- | --- |
| Data lake | S3 | Raw + processed feature snapshots |
| Data versioning | DVC | Reproducible data references in git |
| Validation | Great Expectations | Fail pipeline on schema/distribution issues |
| Experiment tracking | MLflow | Params, metrics, artifacts, lineage |
| Model registry | MLflow Registry | Staging → Production promotion |
| Real-time serving | FastAPI on EKS | `/predict`, `/explain`, `/health`, `/metrics` |
| Batch serving | AWS Lambda | S3-event-triggered scoring |
| Monitoring | Prometheus + Grafana | SRE + ML dashboards |
| Drift detection | Evidently | Scheduled drift reports vs baseline |
| Alerting | Alertmanager → Slack | Errors, latency, drift |
| Orchestration | Airflow / Step Functions | Retraining pipelines |
| LLM explanation | LangChain + FAISS / Bedrock | RAG over policy KB |
| CI | GitHub Actions + Jenkinsfile | Lint, test, train, scan |
| CD | Argo CD or GH Actions | Image build → EKS rollout |
| Infra | Terraform | All AWS resources |

## Data flow — real-time prediction

1. Client posts application JSON to `/predict`.
2. Pydantic validates schema.
3. Feature transformer hydrates engineered features (no online feature store yet; precomputed lookups in Phase 6 if needed).
4. Model (loaded once at startup from MLflow registry) returns `P(default)`.
5. Decision rule applies thresholds → `APPROVE | REVIEW | DENY`.
6. Audit log written: request_id, model_version, features, score, decision.
7. Prometheus metrics updated.

## Data flow — explanation

1. Client posts prediction context (or request_id) to `/explain`.
2. SHAP computes per-feature contributions.
3. Top-K drivers (by |SHAP|) drive a RAG query.
4. Vector store returns matching policy sections.
5. LLM composes plain-English explanation, citing policy section IDs.
6. Output validated for hallucinated sections (cite-checking against retrieved docs).

## Data flow — drift-triggered retraining

1. CronJob (or Airflow daily DAG) pulls last-N days production features.
2. Evidently compares to training baseline.
3. If drift score > threshold OR weekly schedule fires:
   - Re-ingest fresh data.
   - Re-run feature pipeline.
   - Train candidate model.
   - Evaluate: AUC + fairness gates.
   - If pass: register to Staging, post Slack summary, await manual promotion (or auto-promote with canary).
4. Canary: 10% traffic to new model for 30 min; if error rate / latency stable, promote to 100%.

## Security model

- Service accounts on EKS use IRSA → least-privilege IAM roles.
- Secrets via AWS Secrets Manager + external-secrets-operator (no plain K8s Secrets).
- All S3 buckets private + server-side encrypted.
- No PII in MLflow params/tags; features hashed where needed.
- TLS everywhere (cert-manager + Let's Encrypt on EKS).
- Network: private subnets for compute; public ALB only.

## Decision log

See [adr/](adr/) for individual decisions (added as we go).
