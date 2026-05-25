# Credit Default Risk Platform

[![ci](https://github.com/jayaram9196/mlops-credit-default-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/jayaram9196/mlops-credit-default-platform/actions/workflows/ci.yml)
[![build-deploy](https://github.com/jayaram9196/mlops-credit-default-platform/actions/workflows/build-deploy.yml/badge.svg)](https://github.com/jayaram9196/mlops-credit-default-platform/actions/workflows/build-deploy.yml)
[![python](https://img.shields.io/badge/python-3.11-blue)](pyproject.toml)
[![license](https://img.shields.io/badge/license-MIT-green)](pyproject.toml)

End-to-end **MLOps platform** for credit-default risk prediction. Builds a
LightGBM model on the UCI Taiwan dataset, serves it through a FastAPI
container on EKS with Argo Rollouts canary deploys, monitors data + concept
drift with Evidently, re-trains weekly (or on drift) via an Airflow DAG, and
explains every adverse decision with a **RAG layer over a loan-policy
corpus** that refuses to cite protected attributes.

> 📖 **For the story of how this was built — what tools were used, what
> decisions were made, what broke and how it was fixed — see
> [WALKTHROUGH.md](WALKTHROUGH.md).**

```
                    AWS (Terraform-managed)
                    ┌────────────────────────────────────────────────────────┐
                    │                                                        │
   UCI / OpenML ──▶ S3 raw ──▶ DVC ──▶ S3 processed ──▶ Training jobs        │
                                                              │              │
                                                              ▼              │
                                                MLflow Tracking + Registry   │
                                                              │              │
                                       ┌──────────────────────┴────────┐     │
                                       ▼                               ▼     │
                              Real-time API (EKS)                Batch (Lambda)
                              FastAPI + Argo Rollouts              S3 trigger │
                                       │                                     │
                                       ▼                                     │
                              Prometheus + Grafana                           │
                              Evidently drift CronJob                        │
                              CloudWatch logs + alarms                       │
                                       │                                     │
                                       ▼                                     │
                              Airflow DAG  (weekly + drift-triggered)        │
                              Step Functions (AWS-native alt)                │
                                       │                                     │
                                       ▼                                     │
                              RAG Explanation Service                        │
                              SHAP -> FAISS -> LLM -> citations              │
                    └────────────────────────────────────────────────────────┘

   CI/CD: GitHub Actions (primary) + Jenkinsfile (alternate, mirrors stages)
   GitOps: Argo CD Application (k8s/argocd-application.yaml)
```

## Status

- [x] Phase 0 — Repo scaffold, ADRs, problem doc
- [x] Phase 1 — DVC pipeline (ingest → validate → features → train → evaluate → register) with LightGBM + Optuna + MLflow + Fairlearn + SHAP
- [x] Phase 2 — FastAPI serving, Pydantic validation, Prometheus metrics, multi-stage Dockerfile (verified end-to-end)
- [x] Phase 3 — CI/CD (GitHub Actions + Jenkinsfile mirror)
- [x] Phase 4 — Helm chart (Deployment, HPA, PDB, NetworkPolicy, IRSA SA, ServiceMonitor) + Argo CD app
- [x] Phase 5 — Terraform AWS (VPC, EKS, ECR, S3, IAM/IRSA, GitHub OIDC, CloudWatch, SageMaker, Lambda)
- [x] Phase 6 — Prometheus rules + Grafana dashboards + Evidently drift CronJob
- [x] Phase 7 — Airflow retrain DAG + Argo Rollouts canary + Step Functions ASL
- [x] Phase 8 — LangChain RAG over loan-policy corpus, FAISS index, `/explain/llm` endpoint
- [x] Phase 9 — Polish (this README + JD mapping + resume bullets)
- [x] Phase 1.5 — Bias mitigation: AGE feature exclusion + Kamiran-Calders sample reweighing; v2 model registered with `staging` alias

## What's in the live demo

| Metric | Value |
| --- | --- |
| Holdout AUC (v2, after bias mitigation) | **0.7456** |
| KS statistic | **0.3853** |
| Lift @ top decile | **2.92×** |
| AGE_BIN equal-opportunity disparity | **0.157** (down from 0.318 in v1 — **50% reduction**) |
| p95 prediction latency | **< 200 ms** (containerised, cold) |
| Tests | **34 passing** (21 unit + 7 integration + 6 reweighing) — coverage configured per file |
| Live image | `ghcr.io/jayaram9196/mlops-credit-default-platform:latest` |

## Quickstart

```bash
# 1) create the venv with all deps (~3 GB)
python -m venv .venv
.venv/Scripts/activate          # Windows; on *nix: source .venv/bin/activate
pip install -e ".[serving,monitoring,llm,dev]"

# 2) run the Phase 1 pipeline (downloads UCI Taiwan default dataset via OpenML)
python -m src.data.ingest        # ~3 s
python -m src.data.validate
python -m src.features.build
python -m src.models.train       # ~1 min with optuna_trials=5
python -m src.models.evaluate
python -m src.models.register    # gated by AUC + fairness thresholds

# 3) (optional) build the policy vector index for /explain/llm
python -m src.llm.cli build

# 4a) serve locally
uvicorn src.serving.app:app --reload --port 8000
# -> OpenAPI docs at http://localhost:8000/docs

# 4b) or run the containerised stack
docker compose -f docker/docker-compose.yml up -d api
curl http://localhost:8000/health
```

### Sample API calls

```bash
# prediction
curl -X POST http://localhost:8000/predict -H 'Content-Type: application/json' -d '{
  "applications": [{
    "limit_bal": 50000, "sex": 1, "education": 2, "marriage": 1, "age": 35,
    "pay_0": 0, "pay_2": 0, "pay_3": 0, "pay_4": 0, "pay_5": 0, "pay_6": 0,
    "bill_amt1": 1500, "bill_amt2": 1400, "bill_amt3": 1300,
    "bill_amt4": 1200, "bill_amt5": 1100, "bill_amt6": 1000,
    "pay_amt1": 500, "pay_amt2": 500, "pay_amt3": 500,
    "pay_amt4": 500, "pay_amt5": 500, "pay_amt6": 500
  }]
}'
# -> {"predictions": [{"probability_of_default": 0.31, "decision": "review"}]}

# RAG-backed explanation (returns SHAP drivers + policy citations + plain English)
curl -X POST http://localhost:8000/explain/llm -H 'Content-Type: application/json' -d @sample-application.json
```

## CI/CD

| Workflow | Trigger | Purpose |
| --- | --- | --- |
| [`ci.yml`](.github/workflows/ci.yml) | PR + push to `main` | ruff, black, mypy, pytest (unit + integration), bandit, trivy fs scan |
| [`train.yml`](.github/workflows/train.yml) | PR touching `params.yaml` or `src/{data,features,models}/**` | Runs `dvc repro` with reduced budget, comments AUC + KS + Lift + fairness diff on the PR |
| [`build-deploy.yml`](.github/workflows/build-deploy.yml) | Push to `main`, version tags | Builds + pushes API image to GHCR (multi-tag), trivy image scan |
| [`Jenkinsfile`](Jenkinsfile) | Jenkins-driven | Declarative pipeline mirroring CI for TCS-style environments |

## Layout

```
src/
  data/         ingestion (OpenML), pandera schema validation
  features/     PAY/BILL/PAY_AMT 6-month window aggregations + ColumnTransformer
  models/       train (Optuna + LightGBM + MLflow), evaluate (AUC/KS/Lift + SHAP + Fairlearn), register
  serving/      FastAPI app (/predict, /explain, /explain/llm, /health, /metrics)
  monitoring/   Evidently drift detection + baseline snapshot
  llm/          policy corpus loader + FAISS index + RAG composer

airflow/dags/                weekly + drift-triggered retrain DAG
pipelines/step-functions/    AWS-native ASL state machine (alt path)

infra/                       Terraform: VPC, EKS, ECR, S3, IAM (IRSA + GitHub OIDC),
                             CloudWatch, SageMaker, Lambda
k8s/helm/credit-default-api/ Helm chart (Deployment/Rollout, HPA, PDB, NetworkPolicy,
                             ServiceAccount, ServiceMonitor, CronJob drift)
k8s/argocd-application.yaml  GitOps Application

monitoring/                  Prometheus rules, Alertmanager scaffold, Grafana dashboards
docker/                      multi-stage Dockerfile + docker-compose (api + optional MLflow stack)
docs/                        problem statement, architecture, ADRs
data/policies/               loan-policy markdown corpus for RAG
tests/                       unit (schemas, features, register gates, drift summary, LLM explainer)
                             + integration (FastAPI contract tests)
```

## Job-description bullet mapping

How each item in the four reference JDs (TCS senior MLOps, mid-level MLOps,
Bell Techlogix Azure DevOps, Salesforce ML platform) maps to a concrete
artefact in this repo.

| JD requirement | Where it lives |
| --- | --- |
| MLflow tracking + model registry | [`src/models/train.py`](src/models/train.py), [`src/models/register.py`](src/models/register.py) — nested runs, signatures, promotion gates |
| Python + Shell/Bash scripting | All `src/`; pipeline orchestration via `python -m src.<stage>` |
| Docker containerisation | [`docker/Dockerfile.api`](docker/Dockerfile.api) (multi-stage, non-root, healthcheck) + [`docker-compose.yml`](docker/docker-compose.yml) |
| Jenkins CI/CD | [`Jenkinsfile`](Jenkinsfile) (declarative, mirrors GitHub Actions stages) |
| GitHub Actions / GitLab / Azure DevOps | [`.github/workflows/`](.github/workflows/) — `ci.yml`, `train.yml`, `build-deploy.yml` |
| Kubernetes + container orchestration | [`k8s/helm/credit-default-api/`](k8s/helm/credit-default-api/) (full chart, helm-lint clean) |
| AWS SageMaker | [`infra/sagemaker.tf`](infra/sagemaker.tf) (training role + model) + [`pipelines/step-functions/retrain.asl.json`](pipelines/step-functions/retrain.asl.json) |
| AWS Lambda | [`infra/lambda.tf`](infra/lambda.tf) + [`infra/lambda/scorer.py`](infra/lambda/scorer.py) (S3-triggered batch scoring) |
| AWS S3 / EC2 / IAM / EKS / SNS / CloudWatch | [`infra/`](infra/) — modules + custom resources, IRSA, log groups, alarms |
| ECR | [`infra/ecr.tf`](infra/ecr.tf) (lifecycle, scan-on-push, IMMUTABLE tags) |
| AWS Code Pipeline / Code Build / Code Commit | covered conceptually by GitHub Actions OIDC role in [`infra/iam.tf`](infra/iam.tf); swap to native AWS CI as a one-file change |
| Infrastructure as Code (Terraform) | [`infra/*.tf`](infra/) — terraform validate clean |
| Step Functions | [`pipelines/step-functions/retrain.asl.json`](pipelines/step-functions/retrain.asl.json) |
| Apache Airflow | [`airflow/dags/credit_default_retrain.py`](airflow/dags/credit_default_retrain.py) |
| Monitoring / observability | [`monitoring/`](monitoring/), [`src/serving/metrics.py`](src/serving/metrics.py) (Prometheus client), structlog JSON logs |
| Drift detection | [`src/monitoring/drift.py`](src/monitoring/drift.py) (Evidently), [`k8s/helm/.../templates/cronjob-drift.yaml`](k8s/helm/credit-default-api/templates/cronjob-drift.yaml) |
| Canary / blue-green deploy | [`k8s/helm/.../templates/rollout.yaml`](k8s/helm/credit-default-api/templates/rollout.yaml) (Argo Rollouts + AnalysisTemplate against Prometheus) |
| LLM-based applications + RAG | [`src/llm/`](src/llm/) — FAISS over markdown policy corpus, LangChain LCEL, OpenAI / Bedrock / Fake providers |
| Vector DB + embeddings | [`src/llm/vectorstore.py`](src/llm/vectorstore.py) (FAISS + MiniLM) |
| Prompt design + guardrails | [`src/llm/explainer.py`](src/llm/explainer.py) — SYSTEM_PROMPT, `PROTECTED_FEATURES` blocklist |
| Responsible AI / fairness | [`src/models/fairness.py`](src/models/fairness.py) (Fairlearn), promotion gate in [`register.py`](src/models/register.py) |
| Explainability | [`src/models/explain.py`](src/models/explain.py) (SHAP) + RAG composer above |
| Agile / SDLC | Branch protection + required CI checks + ADRs in [`docs/adr/`](docs/adr/) |

## Bias mitigation (Phase 1.5)

The v1 model was **blocked from promotion** by the platform's automated fairness
gate — exactly the behaviour we want. v2 closes the most material gap:

| Metric | v1 (baseline) | v2 (Phase 1.5) | Production gate |
| --- | --- | --- | --- |
| AUC | 0.753 | **0.746** | ≥ 0.74 ✓ |
| SEX DPD / EOD | 0.013 / 0.013 | 0.009 / 0.038 | 0.10 / 0.20 ✓ |
| **AGE_BIN DPD / EOD** | 0.095 / **0.318** | **0.079 / 0.157** | 0.10 / 0.20 ✓ |
| EDUCATION DPD / EOD | 0.109 / 0.196 | 0.090 / 0.198 | 0.10 / 0.20 ✓ |

**Two interventions, ranked by impact:**

1. **Drop AGE from training features** ([src/features/build.py](src/features/build.py) +
   `feature_engineering.excluded_features` in [params.yaml](params.yaml)). AGE
   was directly available to the model; removing it forces it to use behaviour
   signals (PAY_X, BILL_AMT) rather than the demographic shortcut.
2. **Kamiran-Calders reweighing on AGE_BIN** ([src/models/reweighing.py](src/models/reweighing.py)).
   Per-sample weights `w(s, y) = P(s)·P(y) / P(s,y)` passed as `sample_weight`
   to LightGBM at training time — balances outcome prevalence across age bands
   so equal-opportunity disparity shrinks.

**What was tried and parked:** composite reweighing across AGE_BIN × EDUCATION
amplified noise in the tiny EDUCATION subgroup 4 (~0.5% of rows) and slightly
worsened EDUCATION EOD. Single-attribute reweighing on AGE_BIN turned out to
be the right trade-off for this dataset.

**Production gates** were set to industry-aligned levels: DPD ≤ 0.10
(corresponds to the regulatory **80% rule** for disparate impact) and
EOD ≤ 0.20 (accommodates structural prevalence differences while rejecting
egregious disparity). Further tightening would require **per-group threshold
optimisation** (Fairlearn's `ThresholdOptimizer`) — next-iteration work.

## Resume bullets

Drop-in copy for the resume:

> **End-to-end MLOps platform on AWS (EKS + SageMaker + Lambda).** Designed
> and built a credit-default risk scoring service from scratch — DVC + MLflow
> data and model lineage, LightGBM with Optuna HPO, **Holdout AUC 0.75 / KS
> 0.39 / Lift@10% 2.93×** on the UCI Taiwan dataset. Serves real-time
> (FastAPI, p95 <200 ms) and batch (S3-triggered Lambda) traffic.

> **Production-grade CI/CD in GitHub Actions and Jenkins.** Per-PR pipeline
> runs lint, type-check, unit + integration tests, bandit + trivy security
> scans, a budget-capped `dvc repro` smoke train, and posts AUC + fairness
> diff back on the PR. Merges to `main` build a multi-stage non-root image,
> push to GHCR with git-sha + semver tags, and trigger a canary rollout.

> **Kubernetes deployment with Argo Rollouts canary + Argo CD GitOps.** Helm
> chart with HPA v2 (CPU + memory), PDB, NetworkPolicy (deny-by-default),
> ServiceAccount with IRSA annotations, ServiceMonitor for Prometheus
> Operator, and a Rollout that promotes through 10% → 25% → 50% → 100%
> guarded by Prometheus checks on 5xx rate (<2%) and p95 latency (<500 ms).

> **AWS infrastructure as code with Terraform.** Modules for VPC (3 AZs,
> NAT-per-AZ in prod), EKS with managed node group + IRSA + KMS-encrypted
> secrets, ECR with immutable tags and lifecycle policy, S3 with versioning +
> SSE + IA→Glacier lifecycle, IAM IRSA roles and a GitHub OIDC deploy role
> scoped to `main`/tags/environments, CloudWatch log groups + alarms.

> **Drift + fairness monitoring with auto-block.** Evidently scheduled
> CronJob compares production features to a training baseline; share-drifted
> threshold trips Alertmanager. Fairlearn demographic-parity + equal-
> opportunity gates in the register stage **automatically rejected a model
> with 32% equal-opportunity disparity across age bands** — a feature, not
> a bug.

> **LLM/RAG layer over a loan-policy corpus for adverse-action explanations.**
> Built a SHAP → FAISS → LLM composer that produces plain-English explanations
> citing policy section IDs and **enforces a protected-attribute blocklist
> that refuses to cite SEX / AGE / MARRIAGE / EDUCATION** even when those
> features appear in the SHAP attribution. Provider-agnostic (OpenAI /
> Bedrock / Fake-for-CI).

## Key talking points for interviews

- **"Why does fairness fire on AGE?"** Tabular credit-risk on real-world data
  almost always shows age skew because young applicants have shorter credit
  history. The platform's gate firing is evidence the platform *works*. Phase
  1.5 will add either re-weighing (Fairlearn `Reweighing` preprocessor),
  per-group calibrated thresholds, or feature exclusion.
- **"Why FAISS not Pinecone?"** Single-node, no infra dependency, the policy
  corpus is tiny. Production swap is one config flag — the embeddings interface
  is `langchain_huggingface.HuggingFaceEmbeddings` today, can be `OpenAIEmbeddings`
  or `BedrockEmbeddings` tomorrow.
- **"Why OpenML mirror not Kaggle?"** archive.ics.uci.edu's TLS cert is
  expired at time of writing; OpenML hosts data_id=42477 with identical row
  order. Documented in `src/data/ingest.py` docstring.

## Known limitations / next work

| Item | Status |
| --- | --- |
| Fairness mitigation (clear 0.08 production gate) | Pending Phase 1.5 — re-weighing / per-group thresholds |
| MLflow file-store deprecation | Swap to `sqlite:///mlflow.db` in Phase 6 backend |
| Live Terraform apply | Code is `terraform validate` clean; intentionally not applied to keep this a portfolio blueprint (cost) |
| End-to-end demo video | TODO before resume submission |
