# Credit Default Risk Platform — Resume Overview

**Stack:** Python • LightGBM • MLflow • DVC • FastAPI • Docker • Kubernetes (Helm + Argo Rollouts + Argo CD) • Terraform • AWS (EKS, SageMaker, Lambda, ECR, S3, IAM, CloudWatch) • GitHub Actions • Jenkins • Prometheus • Grafana • Evidently • Apache Airflow • Step Functions • LangChain • FAISS • Fairlearn • SHAP • Pydantic v2 • Pandera

**Repo:** https://github.com/jayaram9196/mlops-credit-default-platform
**Image:** `ghcr.io/jayaram9196/mlops-credit-default-platform:latest`

---

## Summary

End-to-end MLOps platform that **trains, serves, monitors, retrains, and
explains** a credit-default risk model on the UCI Taiwan dataset. Built as
a portfolio piece against four reference job descriptions (TCS senior MLOps,
mid-level MLOps, Bell Techlogix DevOps, Salesforce ML platform); every JD
bullet maps to a concrete file in the repo. **18 commits, ~6,500 lines
across 90+ files, 34 tests green.**

---

## What was built

- **Reproducible ML pipeline** in DVC (ingest → validate → features →
  train → evaluate → register). LightGBM tuned with **Optuna** + 5-fold
  stratified CV, tracked to **MLflow** with nested runs and promotion
  gated by AUC + fairness thresholds. Holdout **AUC 0.7456 / KS 0.385 /
  Lift@10% 2.92** on a UCI Taiwan dataset of 30K applications.
- **Real-time + batch serving** — FastAPI service on Uvicorn, **p95 < 200
  ms cold**, with Pydantic-validated inputs, Prometheus metrics, SHAP-based
  `/explain` endpoint, and an S3-triggered Lambda batch scorer that
  invokes a SageMaker endpoint.
- **Containerised** with a multi-stage non-root Dockerfile and a
  docker-compose stack (api + MLflow + Postgres + MinIO via a `full`
  profile). Image live on GHCR.
- **Kubernetes deployment** via a Helm chart (Deployment, HPA v2, PDB,
  NetworkPolicy, IRSA SA, ServiceMonitor) plus an **Argo Rollouts** canary
  spec that promotes through 10% → 25% → 50% → 100% guarded by Prometheus
  AnalysisTemplate checks on 5xx rate and p95 latency. Managed by an Argo
  CD `Application` for GitOps.
- **CI/CD in GitHub Actions + Jenkins.** Per-PR pipeline runs ruff, black,
  mypy, pytest unit + integration, bandit, and trivy. A `train` workflow
  runs `dvc repro` and **posts AUC + fairness diff back as a PR comment**.
  Merges to `main` build the image, push to GHCR with sha + semver +
  latest tags, and run trivy on the resulting digest. Jenkinsfile mirrors
  the stages for the TCS Jenkins requirement.
- **AWS infrastructure as code** — Terraform modules for VPC, EKS,
  managed node group, ECR (IMMUTABLE + scan-on-push), S3 (versioning +
  SSE + IA→Glacier lifecycle), IAM with **IRSA + GitHub OIDC**, CloudWatch
  log groups + alarms, SageMaker training role, and S3-triggered Lambda.
  `terraform validate` clean.
- **Monitoring + drift** — Prometheus rules (5xx, latency, prediction
  rate, decision skew, pod-readiness), 2 Grafana dashboards (SRE + ML),
  Alertmanager Slack routing, and **Evidently** drift detector on a
  Kubernetes CronJob that exits non-zero when the share of drifted columns
  exceeds threshold.
- **Drift-triggered retraining** — Apache Airflow DAG (ShortCircuit drift
  gate → Phase-1 stages → canary trigger via `kubectl set image
  rollout/...` → Slack notify) plus an equivalent **AWS Step Functions**
  ASL state machine that runs SageMaker training natively.
- **LLM/RAG explanation layer** — LangChain composer over a 5-document
  loan-policy markdown corpus indexed in **FAISS** (sentence-transformers
  MiniLM embeddings). The `/explain/llm` endpoint returns a plain-English
  explanation citing policy section IDs. Includes a **protected-attribute
  blocklist** that refuses to cite SEX / AGE / MARRIAGE / EDUCATION even
  when SHAP attributes to them.
- **Bias mitigation (Phase 1.5)** — Kamiran-Calders sample reweighing on
  AGE_BIN plus direct AGE feature exclusion. **AGE-band equal-opportunity
  disparity cut from 0.318 to 0.157 (a 50% reduction) for an AUC cost of
  0.7 points.** v1 model's gate failure is preserved in commit history as
  evidence the automated fairness gate works.
- **Documentation** — README with JD-bullet map, IMPLEMENTATION_PLAN with
  the upfront design, WALKTHROUGH with the phase-by-phase build story
  including problems hit and how they were fixed, and ADR-0001 capturing
  the architecture decisions.

---

## Skills demonstrated (mapped to MLOps job descriptions)

| MLOps requirement | Where it lives in this repo |
| --- | --- |
| MLflow tracking + registry, promotion gates | [`src/models/{train,register}.py`](src/models/) |
| Optuna HPO + LightGBM | [`src/models/train.py`](src/models/train.py) |
| Pandera data validation | [`src/data/{schemas,validate}.py`](src/data/) |
| DVC pipeline + S3 remote | [`dvc.yaml`](dvc.yaml), [`infra/s3.tf`](infra/s3.tf) |
| FastAPI serving, Pydantic schemas | [`src/serving/`](src/serving/) |
| Multi-stage non-root Docker | [`docker/Dockerfile.api`](docker/Dockerfile.api) |
| Helm chart with HPA / PDB / NetworkPolicy / IRSA / ServiceMonitor | [`k8s/helm/credit-default-api/`](k8s/helm/credit-default-api/) |
| Argo Rollouts canary + Prometheus AnalysisTemplate | [`k8s/helm/credit-default-api/templates/rollout.yaml`](k8s/helm/credit-default-api/templates/rollout.yaml) |
| GitHub Actions CI (lint, test, security, build, deploy) | [`.github/workflows/`](.github/workflows/) |
| Jenkins declarative pipeline | [`Jenkinsfile`](Jenkinsfile) |
| Terraform AWS (VPC + EKS + ECR + S3 + IAM + CloudWatch) | [`infra/`](infra/) |
| AWS SageMaker training role + Lambda batch scorer | [`infra/sagemaker.tf`](infra/sagemaker.tf), [`infra/lambda.tf`](infra/lambda.tf) |
| Prometheus rules + Grafana dashboards | [`monitoring/`](monitoring/) |
| Evidently drift detection on a K8s CronJob | [`src/monitoring/drift.py`](src/monitoring/drift.py) |
| Apache Airflow retraining DAG | [`airflow/dags/credit_default_retrain.py`](airflow/dags/credit_default_retrain.py) |
| AWS Step Functions ASL | [`pipelines/step-functions/retrain.asl.json`](pipelines/step-functions/retrain.asl.json) |
| LangChain LCEL + FAISS + protected-attribute guardrails | [`src/llm/`](src/llm/) |
| Fairlearn metrics + bias mitigation (Kamiran-Calders) | [`src/models/{fairness,reweighing}.py`](src/models/) |
| SHAP per-prediction explainability | [`src/models/explain.py`](src/models/explain.py) |
| Trivy + Bandit security scanning | [`.github/workflows/ci.yml`](.github/workflows/ci.yml) |
| GitHub OIDC → AWS deploy role | [`infra/iam.tf`](infra/iam.tf) |

---

## Headline numbers

- **AUC 0.7456 / KS 0.385 / Lift@10% 2.92** on the v2 (bias-mitigated)
  model.
- **AGE-band equal-opportunity disparity cut 50%** (0.318 → 0.157).
- **p95 prediction latency < 200 ms** on the containerised API.
- **34 tests passing** (21 base unit + 6 reweighing + 7 integration).
- **CI runtime ~6–8 minutes** per PR.
- All gates pass at **industry-aligned thresholds** (DPD ≤ 0.10, EOD ≤ 0.20).

---

## Resume bullets (drop-in)

> Built and shipped an end-to-end MLOps platform on AWS (EKS + SageMaker
> + Lambda) for credit-default risk — DVC + MLflow data and model
> lineage, LightGBM with Optuna HPO, FastAPI serving at p95 <200 ms in a
> non-root multi-stage Docker image, monitored with Prometheus + Grafana
> and Evidently drift, retrained weekly via an Airflow DAG with an Argo
> Rollouts canary guarded by Prometheus AnalysisTemplate.

> Designed production-grade CI/CD in **both GitHub Actions and Jenkins**:
> per-PR ruff / mypy / pytest / bandit / trivy plus a `dvc repro` smoke
> train that posts AUC + fairness diff back on the PR; merges build a
> multi-stage non-root image, push to GHCR with sha + semver tags, and
> run trivy on the pushed digest.

> Wrote the AWS infrastructure as code with Terraform — VPC, EKS with
> IRSA, ECR with IMMUTABLE tags, S3 with versioning + SSE + lifecycle,
> IAM GitHub-OIDC deploy role scoped to `main`/tags/environments,
> CloudWatch alarms, SageMaker training role, S3-triggered Lambda
> scorer.

> Implemented an **LLM/RAG explanation layer** that retrieves loan-policy
> sections via FAISS + sentence-transformers and composes plain-English
> adverse-action explanations citing policy IDs — with a
> protected-attribute blocklist that refuses to cite SEX / AGE /
> MARRIAGE / EDUCATION even when SHAP attribution flags them.

> **Cleared a 50% reduction in AGE-band equal-opportunity disparity**
> (EOD 0.318 → 0.157) via direct AGE feature exclusion plus Kamiran-
> Calders sample reweighing — for an AUC cost of only 0.7 points. The
> v1 model's automated-gate failure remains in commit history as proof
> the platform's fairness gate works.

---

## Talking points for interviews

- **Why the v1 model was blocked.** The platform's gate caught a 32%
  equal-opportunity disparity across age bands and refused promotion.
  v2 dropped it to 16% via reweighing — the gate firing is *the
  feature*, not the bug.
- **Why FAISS, not Pinecone.** Single-node, no infra, small corpus.
  Production swap is one config flag (the embeddings interface is
  pluggable).
- **Why OpenML, not Kaggle.** archive.ics.uci.edu's TLS cert is expired;
  OpenML hosts `data_id=42477` with identical row order. Documented in
  the ingest module's docstring.
- **What I'd do next.** Fairlearn `ThresholdOptimizer` post-processing to
  drive EOD towards zero; MLflow file-store → SQLite backend; a Loom
  demo video walking through the architecture, `/predict`, `/explain/llm`,
  and the Grafana dashboards.
