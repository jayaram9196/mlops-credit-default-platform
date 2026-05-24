# AI-Powered Loan Default Risk Platform — Implementation Plan

> **Purpose:** End-to-end MLOps portfolio project mapped to MLOps/DevOps job descriptions (TCS, Virtusa-style mid-level, Bell Techlogix, Salesforce). Every implementation choice maps back to a specific JD bullet.

---

## 1. Problem Framing

**Business problem.** A lender wants to predict probability of default at loan-application time so it can approve, reject, or send to manual review. This is a regulated domain (fair-lending laws, GDPR-style data rights) so every prediction must be **explainable** and **auditable**.

**Why this problem.**
- Tabular ML lifecycle (training, validation, drift) — covers core MLOps JD asks.
- Regulated domain → forces fairness checks, audit logs, explainability — senior MLOps signal.
- Adds an LLM/RAG explanation layer → covers Salesforce + Bell Techlogix LLM bullets.
- Real-time + batch scoring patterns → covers both "SageMaker endpoint" and "Lambda batch" asks.

**Dataset.** UCI Machine Learning Repository — [Default of Credit Card Clients](https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients) (Taiwan, 2005). 30,000 rows, fetched via the `ucimlrepo` Python package (no auth). Single table with 6-month time-series fields (`PAY_X`, `BILL_AMTX`, `PAY_AMTX`) that drive non-trivial window-aggregation feature engineering.

**Success metrics.**
- Model: AUC, KS statistic, fairness disparity across protected attributes.
- Platform: p95 prediction latency, deployment frequency, MTTR, drift detection time-to-alert.

---

## 2. Target Architecture

```
                    AWS Cloud (Terraform-managed)
                    ───────────────────────────────────────────────
  Data ──> S3 (raw) ──> DVC ──> S3 (processed) ──> Training
                                                       │
                                                       v
                                          MLflow Tracking + Registry
                                                       │
                                       ┌───────────────┴────────────┐
                                       v                            v
                                Real-time API                Batch (Lambda)
                              (FastAPI on EKS)
                                       │
                                       v
                            Prometheus + Grafana
                            Evidently (drift)
                            CloudWatch logs
                                       │
                                       v
                            Airflow / Step Functions
                            (drift-triggered retraining)
                                       │
                                       v
                            RAG Explanation Service
                            (LangChain + FAISS / Bedrock)

  CI/CD: GitHub Actions (primary) + Jenkinsfile (alternate)
  IaC:   Terraform modules (vpc, eks, ecr, iam, s3, sagemaker, lambda)
```

---

## 3. Phased Plan

Each phase ends with a demoable artifact. You can stop at any phase and still have something to show.

### Phase 0 — Foundation (Week 1)
- Repo scaffold (this commit).
- Problem doc + architecture diagram.
- Dataset downloaded + versioned in DVC.
- Pre-commit hooks (ruff, black, mypy, nbstripout).

**Deliverable:** Repo with README, plan, problem doc, raw data tracked.

### Phase 1 — Core ML Pipeline (Week 2)
- DVC stages: ingestion → validation → feature engineering → training → evaluation → registration.
- Great Expectations for data validation (fails pipeline on schema/distribution issues).
- XGBoost + LightGBM with Optuna hyperparam tuning.
- MLflow: params, metrics, artifacts, signatures, environment.
- Fairness checks: Fairlearn across `CODE_GENDER`, age bins.
- SHAP: global + per-prediction explanations.
- pytest unit tests for transforms + model invariants.
- Promotion script: only register to "Staging" if AUC and fairness gates pass.

**Deliverable:** `dvc repro` runs end-to-end; MLflow UI shows experiments; registered model.

**JD bullets satisfied:** MLflow, Python, ML lifecycle, data versioning, model registry.

### Phase 2 — Serving + Containerization (Week 3)
- FastAPI service: `/predict` (single + batch), `/explain`, `/health`, `/metrics`.
- Pydantic schemas for validation.
- Load model from MLflow registry at startup.
- Multi-stage Dockerfile.
- docker-compose: api + mlflow-server + postgres + minio.
- pytest + httpx API contract tests; locust load test.
- Structured JSON logging (structlog).

**Deliverable:** `docker compose up` boots full stack locally; OpenAPI docs at `/docs`.

**JD bullets satisfied:** Docker, containerization, ML serving API.

### Phase 3 — CI/CD (Week 4)
- GitHub Actions workflows: `ci.yml` (lint + tests + security scan), `train.yml` (DVC repro on data/params change), `build-deploy.yml` (build + push to ECR + trigger rollout).
- Jenkinsfile equivalent (declarative pipeline, same stages).
- Branch protection: checks must pass + 1 review.
- Trivy + Bandit security scans.
- OIDC to AWS (no long-lived keys).

**Deliverable:** PR triggers checks; merge pushes image to ECR.

**JD bullets satisfied:** CI/CD, Jenkins, GitHub Actions, SDLC.

### Phase 4 — Kubernetes (Week 5)
- Deployment + Service + Ingress + HPA + ConfigMap + Secret + PDB + NetworkPolicy.
- Resource requests/limits, probes, securityContext (non-root).
- Helm chart with dev/staging/prod values.
- Local: kind / minikube; cloud: EKS-ready.
- Optional: Argo CD for GitOps.

**Deliverable:** `helm install` on kind → API reachable, scales under load.

**JD bullets satisfied:** Kubernetes, orchestration, EKS-ready.

### Phase 5 — Cloud Infrastructure (Week 6)
- Terraform modules: vpc, eks, ecr, iam (IRSA), s3, cloudwatch, sagemaker training job, lambda batch scorer.
- Remote state in S3 + DynamoDB lock.
- `make infra-up` / `make infra-down`.

**Deliverable:** `terraform apply` provisions full AWS env; `destroy` cleans up.

**JD bullets satisfied:** AWS (S3, EC2, IAM, EKS, CloudWatch, SageMaker, Lambda), IaC.

### Phase 6 — Monitoring & Drift (Week 7)
- Prometheus scrapes `/metrics`: latency histograms, request counters, error rates, prediction distribution.
- Grafana dashboards: SRE + ML views.
- Evidently AI scheduled job: data + prediction drift vs training baseline → report → S3 + alert.
- Alertmanager → Slack on errors / latency / drift.
- CloudWatch logs.

**Deliverable:** Grafana dashboard; drift report; alert demo.

**JD bullets satisfied:** Monitoring, observability, drift detection, CloudWatch.

### Phase 7 — Retraining Orchestration (Week 8)
- Airflow DAG (or Step Functions): ingest → validate → drift check → retrain → fairness/perf gates → register → canary.
- Canary deployment via Argo Rollouts or weighted Service.
- Slack notification with comparison report.

**Deliverable:** Airflow UI showing retraining DAG; documented promotion workflow.

**JD bullets satisfied:** Automation, model lifecycle, Step Functions.

### Phase 8 — LLM/RAG Explanation Layer (Week 9) — **the differentiator**
- ~20 mock loan policy documents as KB.
- FAISS local / Bedrock Knowledge Bases on cloud.
- LangChain pipeline: model prediction → SHAP top features → RAG retrieval → LLM generates plain-English explanation.
- `POST /explain` endpoint.
- Evaluation: LLM-as-judge + RAGAS.
- Guardrails: input/output validation, prompt-injection defense, PII redaction.

**Deliverable:** Demo: prediction → English explanation citing policy section.

**JD bullets satisfied:** LLM, RAG, vector DB, embeddings, prompt design, Responsible AI.

### Phase 9 — Polish & Resume Artifacts (Week 10)
- README with architecture diagram, demo GIFs, JD-bullet-to-implementation map.
- Demo video (Loom, 5 min).
- Blog post (Medium / dev.to).
- Resume bullets with quantifiable claims.
- GitHub polish: topics, pinned repo, clean commit history.

**Deliverable:** Resume ammo + demo URL + blog URL.

---

## 4. Stop Points

- **MVP** = end of Phase 4 (model + Docker + CI/CD + K8s). Enough to apply to mid-level JDs.
- **Strong** = end of Phase 7. Hits TCS + Bell Techlogix at 90%.
- **Differentiated** = Phase 8. Stands out vs. other applicants.

---

## 5. Operating Assumptions (override anytime)

- **Cloud:** AWS primary. Azure equivalents documented later if needed.
- **Real cloud spend:** Local-first with kind/minikube. Terraform code as a "blueprint" deliverable. Optional: spin up real EKS for screenshots before tearing it down.
- **Dataset:** UCI Default of Credit Card Clients (id=350), Taiwan, 30K rows.
- **Python:** 3.11.
- **Package manager:** `uv` for speed (or pip + venv).
- **OS:** Windows host, WSL or git-bash for `make` commands. Pure-PowerShell fallback if needed.
