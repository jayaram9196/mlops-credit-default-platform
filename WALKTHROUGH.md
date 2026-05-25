# Build Walkthrough — Credit Default Risk Platform

A step-by-step record of how this project was built, what was used, what
decisions were made, what broke along the way, and how each piece was fixed.
Companion to the [README](README.md) (project landing page) and
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) (upfront design).

---

## TL;DR

End-to-end MLOps platform built in nine phases plus one bias-mitigation
follow-up. Trains a LightGBM credit-default model on the UCI Taiwan dataset,
serves it via FastAPI on Kubernetes with Argo Rollouts canary deploys,
monitors data + concept drift with Evidently, retrains weekly via an Airflow
DAG, and explains every adverse decision with a RAG layer over a loan-policy
corpus that refuses to cite protected attributes. Holdout **AUC 0.7456 / KS
0.385 / Lift@10% 2.92** after a Phase 1.5 bias-mitigation pass that cut
AGE-band equal-opportunity disparity by 50%.

**Repo:** https://github.com/jayaram9196/mlops-credit-default-platform
**16 commits total.** All local checks green (mypy, ruff, black, helm-lint,
terraform-validate, pytest 34/34).

---

## Project context

### Why credit-default risk?

Four MLOps job descriptions (TCS senior, JD#1 mid-level, Bell Techlogix
Azure DevOps, Salesforce ML platform) shaped the design. Common bullets:
MLflow, Docker, Kubernetes, CI/CD (Jenkins/GH Actions), AWS (SageMaker,
EKS, Lambda, S3, IAM, CloudWatch), IaC (Terraform), monitoring + drift, and
increasingly LLM/RAG.

Credit-default risk hits the **regulated-tabular** sweet spot: the domain
forces conversations about fairness, audit trails, and explainability that
interviewers love. The Campusx YouTube-sentiment tutorial that many
candidates submit is recognisable — credit-risk + ECOA framing is
differentiated.

### What "done" looks like

| Concern | Target |
| --- | --- |
| Holdout AUC | ≥ 0.74 |
| Fairness (per protected attr) | DPD ≤ 0.10, EOD ≤ 0.20 |
| Real-time p95 latency | < 200 ms |
| CI runtime | < 10 min per PR |
| Helm chart | lints clean; renders deploy + canary |
| Terraform | validates + formats clean |
| Tests | unit + integration green in CI |

---

## Setup story (the unglamorous bits)

These bits aren't in the README but they're real and they cost time. They
also turn into interview talking points.

### 1. Dataset pivot

**Start:** Home Credit Default Risk (Kaggle competition, 300K rows, 7 tables).
The plan called for multi-table aggregation feature engineering.

**Problem:** Kaggle required accepting the competition rules. The user has
multiple Kaggle accounts and the rules-acceptance flow demanded phone
verification on the account that the OAuth flow had picked.

**Pivot:** UCI "Default of Credit Card Clients" (Taiwan, 30K rows, single
table with 6-month time-series columns). No auth at all on UCI.

**Wrinkle:** archive.ics.uci.edu's TLS certificate is expired. `ucimlrepo`'s
direct HTTPS request fails with `SSLCertVerificationError`. **Workaround**:
OpenML hosts the same dataset as `data_id=42477` with generic `x1…x23` column
names that we rename to the canonical UCI schema. Documented in
[src/data/ingest.py](src/data/ingest.py) and ADR-0001.

### 2. Disk space crisis

`pip install -e ".[dev]"` failed mid-install with `OSError: No space left on
device`. Investigation: `df -h /c` showed only **285 MB** free of 219 GB.

Top offenders:
- pip cache: 1.2 GB → purged
- Downloads: 3.6 GB → user cleared
- OneDrive local cache: 3.9 GB → user freed via "Free up space"

After cleanup, 31 GB free. Install resumed and succeeded.

### 3. Windows MAX_PATH on JupyterLab

The `dev` extra originally included `jupyter` (which pulls JupyterLab).
JupyterLab's deeply nested `vendors-node_modules_…js` paths exceed
Windows' 260-character MAX_PATH limit, blocking the install. **Fix**: removed
`jupyter` from the extras; `ipykernel` alone is enough for notebook work
without dragging in JupyterLab's bundles.

### 4. OneDrive on the build context

The project lives at `c:\Users\Jayar\OneDrive\Desktop\Mlops project\…`. The
first Docker build of the API image took **70 minutes** (vs. expected ~10)
because OneDrive's sync handler intercepted every file read in the build
context. Acceptable trade-off (verified subsequently for any rebuild we
needed); the recommendation stands to move to `C:\dev\…` if doing this
again.

### 5. MLflow file-store URI on Windows

`mlflow.set_tracking_uri(f"file://{path.as_posix()}")` produced
`file://C:/…` — which MLflow read as a remote URI (because of the two
slashes plus drive letter) and rejected. **Fix**: `path.as_uri()` produces
`file:///C:/…` (three slashes), which MLflow handles correctly.

---

## Phase-by-phase tour

Each phase ends with a demoable artefact and a green commit.

### Phase 0 — Foundation (commit included in `1aa876e`)

**Goal**: Scaffold the project so subsequent phases can land code without
fighting directory layout.

**Built**:
- `IMPLEMENTATION_PLAN.md` — 10-phase plan with JD-bullet mapping.
- `README.md` — project landing page with status checklist.
- `pyproject.toml` — editable install with extras `[serving, llm, monitoring, dev]`.
- `params.yaml` — all hyperparameters, thresholds, paths in one config file.
- `Makefile`, `.gitignore`, `.gitattributes`, `.pre-commit-config.yaml`.
- `docs/problem-statement.md`, `docs/architecture.md`, `docs/adr/0001-architecture-snapshot.md`.
- Directory structure: `src/{data,features,models,serving,monitoring,llm}/`, `tests/{unit,integration}/`, `infra/`, `k8s/`, `docker/`, `pipelines/`, `notebooks/`, `data/{raw,interim,processed,external}/`.

**Tools**: Python 3.11/3.12 (project supports 3.11–3.13), `setuptools`,
pre-commit (ruff + black + mypy + nbstripout + bandit hooks).

**Decisions** (in `docs/adr/0001-architecture-snapshot.md`):
- AWS as primary cloud (broadest JD coverage).
- Local-first with cloud blueprints (Terraform code is the deliverable, not a
  live infra bill).
- FastAPI not Flask (modern, async, free OpenAPI docs).
- LightGBM primary, XGBoost alternate (both via Optuna HPO).

### Phase 1 — Core ML pipeline (commit `1aa876e`)

**Goal**: Reproducible ingest → train → register pipeline.

**Built** — six DVC stages in `dvc.yaml`:
1. `ingest` — fetch UCI dataset via OpenML, stratified train/holdout split → `data/{raw,interim}/`.
2. `validate` — Pandera schemas on all splits → `reports/validation.json`.
3. `features` — 6-month window aggregations on `PAY_X`, `BILL_AMTX`, `PAY_AMTX`; utilisation ratios; AGE_BIN; sklearn ColumnTransformer fitted on train → `data/processed/{train,holdout}.parquet` + `models/transformer.joblib`.
4. `train` — Optuna HPO (5 trials in smoke mode, 50 in prod) over LightGBM with 5-fold stratified CV; each trial is a nested MLflow run; final fit on the full training set → `models/model.joblib`.
5. `evaluate` — AUC/KS/Lift@10%/Brier/calibration on holdout; SHAP global summary; Fairlearn DPD/EOD across SEX, AGE_BIN, EDUCATION → `reports/metrics.json` + `reports/plots/*.png`.
6. `register` — promotion gates (min AUC, max DPD, max EOD) → `mlflow.sklearn.log_model` + `staging` alias.

**Tools**: `dvc[s3]`, `mlflow`, `lightgbm`, `xgboost`, `optuna`, `pandera`,
`fairlearn`, `shap`, `pyarrow`, `joblib`, `structlog`.

**Decisions**:
- Pandera over Great Expectations (cleaner API, type-safe, modern).
- Per-trial MLflow nested runs (so the Optuna study and the best params share
  a parent run).
- Promotion gated by AUC **and** fairness simultaneously — a high-AUC biased
  model gets blocked.

**Verification**: `dvc repro` runs end-to-end in ~1 minute (5 Optuna trials).
Best CV AUC 0.7833, holdout AUC 0.7532, KS 0.39, Lift@10% 2.93.

**First fairness finding**: AGE_BIN equal-opportunity disparity = **0.318**
(TPR ranges from 0.35 for 26-35 to 0.67 for 66+). The gate correctly
**blocked promotion**. Smoke-test thresholds were widened to 0.5 just to
verify the register code path; production thresholds were retained as a
follow-up (Phase 1.5).

### Phase 2 — FastAPI serving + Docker (commit `1aa876e`)

**Goal**: Stand the model up behind an HTTP API and ship it in a
production-quality container.

**Built**:
- `src/serving/schemas.py` — Pydantic v2 models with `Field(...)` constraints
  (e.g. `sex: int = Field(ge=1, le=2)`).
- `src/serving/inference.py` — `ModelService.load(model_path, transformer_path)`
  with feature pipeline + transformer + SHAP explainer.
- `src/serving/metrics.py` — Prometheus counters + histograms.
- `src/serving/app.py` — FastAPI with `/predict`, `/explain`, `/health`,
  `/metrics`; lifespan loads the model once at startup; telemetry middleware
  attaches a request_id and emits structured JSON logs.
- `docker/Dockerfile.api` — multi-stage build, non-root user, `HEALTHCHECK`.
- `docker/docker-compose.yml` — `api` service + optional `full` profile that
  brings up MLflow, Postgres, MinIO.
- `tests/integration/test_api.py` — 7 contract tests using `httpx.TestClient`.

**Tools**: FastAPI, Uvicorn, Gunicorn, `prometheus-client`, structlog,
Docker BuildKit, docker-compose v2.

**Decisions**:
- Pydantic v2 throughout — input validation at the boundary, no manual checks.
- Load model from joblib at startup (MLflow registry load is the production
  swap; documented in the docstring).
- Single explainer cached on first use to avoid SHAP's per-call setup cost.
- `--exit-code 0` on trivy scans by default (report-only) until a clean dep
  baseline is established.

**Problem hit**: `FeatureArtifacts` was a dataclass defined inside
`src/features/build.py`. Running it via `python -m src.features.build` made
`__main__` the module of record on the pickle, so when the integration tests
tried to `joblib.load` from `pytest.__main__`, the lookup failed.
**Fix**: replaced the dataclass with a plain dict — picklable from any
caller, no module ambiguity. Regenerated the joblib.

**Verification**: live container hits all endpoints; `/predict` returns
`{"probability_of_default": 0.31, "decision": "review"}` for a sample
applicant; SHAP-based `/explain` returns top-5 drivers; p95 ~185 ms on
first call.

### Phase 3 — CI/CD (commits `53d5bb3`, `6afa287`, `b2b0e28`)

**Goal**: Per-PR quality gate + merge-to-main image push, in both GitHub
Actions and Jenkins.

**Built**:
- `.github/workflows/ci.yml` — `lint`, `unit-tests`, `integration-tests`
  (with budget-capped `dvc repro`), `security` (bandit + trivy fs).
- `.github/workflows/train.yml` — triggers on `params.yaml` / `src/{data,features,models}/**` changes, comments AUC/KS/Lift/fairness diff back on the PR via `actions/github-script`.
- `.github/workflows/build-deploy.yml` — on push to `main`, builds with
  `docker/build-push-action`, pushes to `ghcr.io/jayaram9196/mlops-credit-default-platform` with multi-tag (sha-short + semver + latest), then trivy image scan.
- `Jenkinsfile` — declarative pipeline mirroring CI: `setup` → `lint` →
  `unit tests` → `smoke pipeline` → `integration tests` → `docker build + push` → `trivy image scan`. Targets the TCS Jenkins requirement.

**Tools**: GitHub Actions, BuildKit, GHCR, Jenkins, Trivy, Bandit.

**Problems hit (worth knowing for interviews)**:

1. **Cloudfront EOF on BuildKit syntax frontend**. The first
   `docker compose build` failed pulling `docker/dockerfile:1.7`. **Fix**:
   removed the `# syntax=` directive — we don't use features that need it.
2. **Trivy action setup failure**. `aquasecurity/trivy-action@0.28.0` failed
   at the GitHub Actions `Set up job` stage. **Cause**: tag prefix mismatch
   (`v0.28.0` exists, `0.28.0` doesn't). After the `v`-prefix fix, the setup
   still failed. **Final fix**: installed trivy via the official install
   script (`curl -sfL .../install.sh | sh`) and dropped the action
   dependency entirely.
3. **Build-deploy trivy image-tag**. `docker/metadata-action@v5`'s `version`
   output is the first generated tag (usually `main`), so my image ref
   `…:sha-${version}` resolved to `…:sha-main` which doesn't exist. **Fix**:
   switched to the image digest (`@${image-digest}`) — both correct and
   immutable.
4. **CI didn't install the `[llm]` extra** — Phase 8 LLM tests failed at
   import time. **Fix**: added `[llm]` to the install in `ci.yml`.
5. **Mypy caught one real bug**: `LLMExplanation.decision` typed `str` but
   the API response model required `Decision = Literal[...]`. **Fix**:
   tightened the type.

**Verification**: CI runs in ~6–8 minutes per PR; build-deploy pushes the
image to GHCR with green status.

### Phase 4 — Kubernetes (commit `16d6ca0`)

**Goal**: Deploy on Kubernetes with production patterns.

**Built** — Helm chart `k8s/helm/credit-default-api/`:
- `Chart.yaml`, `values.yaml`, `values-prod.yaml`.
- Templates: `deployment.yaml` (probes, securityContext, topology spread),
  `service.yaml`, `ingress.yaml` (nginx + cert-manager), `configmap.yaml`,
  `secret.yaml` (rendered only when non-empty), `hpa.yaml` (CPU + memory),
  `pdb.yaml`, `networkpolicy.yaml` (deny-by-default; ingress only from
  `ingress-nginx`, egress to DNS + 443), `serviceaccount.yaml`
  (IRSA-annotation-ready), `servicemonitor.yaml` (Prometheus Operator),
  `NOTES.txt`.
- `k8s/argocd-application.yaml` — GitOps Application for Argo CD.
- `k8s/README.md` — local kind recipe + EKS recipe + model-loading
  strategies.

**Tools**: Helm 3, Argo CD, Kubernetes 1.30.

**Decisions**:
- Default `modelInit.enabled=false` — image is expected to carry the model;
  `prod.yaml` enables the init-container `aws s3 sync` pattern.
- HPA v2 with both CPU + memory targets (Phase 6 will add custom
  metrics-server backed scaling).
- NetworkPolicy denies all by default.

**Verification**: `helm lint` clean; `helm template` for default mode
renders 7 resources, prod mode renders 9 (adds Ingress + ServiceMonitor).

### Phase 5 — Terraform AWS infra (commit `c119adc`)

**Goal**: Reproducible AWS footprint.

**Built**:
- `versions.tf`, `backend.tf`, `variables.tf`, `outputs.tf`, `locals.tf`.
- `vpc.tf` — `terraform-aws-modules/vpc/aws@~> 5.13`: 3 AZs, public +
  private + intra subnets, NAT (single in staging, per-AZ in prod), EKS
  subnet tags.
- `eks.tf` — `terraform-aws-modules/eks/aws@~> 20.31`: managed node group,
  core addons (coredns, kube-proxy, vpc-cni, ebs-csi, pod-identity),
  KMS-encrypted secrets.
- `ecr.tf` — IMMUTABLE tags, scan-on-push, lifecycle policy.
- `s3.tf` — data + artifacts buckets, versioning, SSE-AES256, public-access
  block, lifecycle (IA → Glacier on the data bucket).
- `iam.tf` — IRSA role for the pod (S3 ro on artifacts + CloudWatch Logs
  write); GitHub OIDC provider + deploy role with sub conditions on
  `main`/tags/environments.
- `cloudwatch.tf` — log groups + JSON-log error metric filter + alarm.
- `sagemaker.tf` — training role + model definition (AWS-native alternate
  training path).
- `lambda.tf` + `lambda/scorer.py` — S3-triggered batch scorer that invokes
  the SageMaker endpoint.
- `envs/{staging,prod}.tfvars` — sizing (t3.medium × 2 staging vs.
  m6i.large × 3-10 prod).
- `bootstrap/main.tf` — one-time state bucket + DDB lock table.
- `infra/README.md` — walkthrough including the GitHub Actions OIDC wiring.

**Tools**: Terraform 1.6+, `hashicorp/aws@~> 5.70`, `terraform-aws-modules/{vpc,eks}/aws`.

**Decisions**:
- Community modules for VPC + EKS (battle-tested), custom code for
  IAM/ECR/S3/Lambda/SageMaker (explicit story).
- Image digest pinning later in build-deploy ties the live image to
  Terraform's `aws_ecr_repository` output.

**Verification**: `terraform fmt -recursive -check` clean;
`terraform init -backend=false && terraform validate` reports Success with
no warnings (after fixing one S3 lifecycle filter and one tag-block
formatting drift).

**Not run live** — the code is the deliverable. `terraform apply` is left
for the user; a portfolio EKS run is ~$73/month for the control plane plus
NAT, so it's a managed exercise rather than a permanent deployment.

### Phase 6 — Monitoring & drift (commits `5f297cf`, `21b5b22`)

**Goal**: Three observability layers — service health, model behaviour,
data drift.

**Built**:
- `monitoring/prometheus/rules.yaml` — recording rules + 5 alerts
  (5xx rate, p95 latency, prediction rate zero, decision skew, pods not
  ready).
- `monitoring/alertmanager/config.example.yaml` — Slack routing.
- `monitoring/grafana/dashboards/credit-default-{sre,ml}.json` — two
  dashboards: SRE (req/s, error rate, latency p50/95/99, HPA, restart rate)
  and ML (decision mix, score histogram, drift gauge, drifted-cols over
  time).
- `src/monitoring/baseline.py` — captures reference parquet snapshot from
  training split.
- `src/monitoring/drift.py` — Evidently `DataDriftPreset`, writes JSON +
  HTML reports, exits non-zero past threshold.
- `k8s/helm/.../templates/cronjob-drift.yaml` — scheduled drift job using
  the same image (toggle via `.Values.drift.enabled`).
- `monitoring/README.md` — wiring guide.

**Tools**: Prometheus + Alertmanager + Grafana (kube-prometheus-stack),
Evidently AI.

**Decisions**:
- Drift CronJob runs on the same image as the API — no separate worker
  image to maintain.
- Report-only by default; failure surfaces via the Kubernetes Job status.

**Verification**: helm-lint clean; with `drift.enabled=true` the chart
renders a CronJob alongside the API resources; 2 new unit tests on the
drift `summarise()` function pass against a fake snapshot.

### Phase 7 — Retraining orchestration + canary (commit `5028290`)

**Goal**: Close the loop — drift detected → retrain → canary deploy with
automated rollback.

**Built**:
- `airflow/dags/credit_default_retrain.py` — weekly DAG: ShortCircuit drift
  gate → ingest → validate → features → train → evaluate → register →
  trigger canary (`kubectl set image rollout/...`) → Slack notify.
- `airflow/requirements.txt`, `airflow/README.md`.
- `pipelines/step-functions/retrain.asl.json` — AWS-native ASL state
  machine: drift Lambda → SageMaker training (`.sync`) → gate Lambda →
  promote-and-canary Lambda → SNS notify. Covers the TCS Step-Functions
  bullet without forcing Airflow.
- `k8s/helm/.../templates/rollout.yaml` — Argo Rollouts spec replaces
  Deployment when `.Values.canary.enabled=true`. AnalysisTemplate runs
  Prometheus checks during each canary step:
  - 5xx rate < 2%
  - p95 latency < 500 ms
  - Five 1-minute checks per step; one failure aborts.
- `values.yaml.canary.steps`: 10% → 25% → 50% → 100% with 5-minute pauses.

**Tools**: Apache Airflow 2.9+, Argo Rollouts, AWS Step Functions, Slack.

**Decisions**:
- Airflow uses `BashOperator` to call the Phase 1 stages so the contract
  between Airflow and the project is loose (the worker doesn't need every
  ML package baked in).
- Both Airflow and Step Functions are first-class — different shops use
  different orchestrators.

**Verification**: helm-lint clean both modes; canary mode renders Rollout +
AnalysisTemplate (Deployment suppressed via `{{- if not .Values.canary.enabled -}}`).

### Phase 8 — LLM/RAG explanation layer (commits `f81047a`, `cdcf0f4`)

**Goal**: The differentiator. Every adverse decision gets a plain-English
explanation grounded in cited policy sections, with protected attributes
explicitly blocklisted.

**Built**:
- `data/policies/{01-05}-*.md` — five plausible policy markdown documents
  with YAML front-matter: credit policy, fair lending (ECOA), adverse
  action notice (FCRA), data subject rights (GDPR Article 22), manual
  review band.
- `src/llm/corpus.py` — parses front-matter + body into LangChain
  `Document`s.
- `src/llm/vectorstore.py` — FAISS over
  `sentence-transformers/all-MiniLM-L6-v2`; `build_index()` +
  `load_index()`.
- `src/llm/explainer.py` — the composer:
  - Calls `model_service.explain(application, top_k=5)` for prob + SHAP.
  - Builds the retrieval query from decision + non-protected drivers only.
  - Renders a guardrailed prompt (`SYSTEM_PROMPT` + `USER_TEMPLATE`).
  - Invokes the LLM (`fake` / `openai` / `bedrock`, configured in
    `params.yaml`). `FakeListLLM` is the default so CI works without keys.
  - `PROTECTED_FEATURES` blocklist refuses to cite SEX / AGE / MARRIAGE /
    EDUCATION even when SHAP attributes to them.
- `src/llm/cli.py` — `python -m src.llm.cli build | search`.
- `src/serving/app.py` — `POST /explain/llm` endpoint with 503 fallback if
  the index isn't built; lazy retriever cache so the API stays light for
  `/predict`-only callers.
- `src/serving/schemas.py` — `LLMExplanationResponse` + `PolicyCitation`.
- `tests/unit/test_llm_explainer.py` — 4 tests with `FakeLLM` and
  `_FakeRetriever`, all deterministic.

**Tools**: LangChain (`langchain`, `langchain-community`, `langchain-openai`,
`langchain-huggingface`, `langchain-text-splitters`), FAISS-CPU,
sentence-transformers.

**Decisions**:
- FAISS local default — single-node, no infra. Production swaps to AWS
  OpenSearch / Bedrock Knowledge Bases.
- `fake` LLM provider for CI — tests don't burn API tokens.
- `PROTECTED_FEATURES` includes both raw names (`SEX`, `AGE`) and OHE
  variants (`SEX_1`, `EDUCATION_4`) so the blocklist survives the
  ColumnTransformer.

**Verification**: `python -m src.llm.cli build` produces a real FAISS
index over the 5 policy docs; a live `/explain/llm` call against an
applicant with PAY_0=2 returns a `review` decision plus citations to
`AA-01 §3.1` and `CP-01 §1.1`; tests pass with the `FakeLLM`.

### Phase 9 — Polish (commit `a3486d1`)

**Goal**: Turn the build into resume ammunition.

**Built**:
- README rewrite: architecture ASCII diagram, status checklist, sample
  curl payloads, CI/CD table, layout, **JD-bullet-to-implementation map**
  (each item links to the file that proves it), ready-to-paste resume
  bullets, interview talking points, known limitations.
- Badges for CI + build-deploy workflows.

**Decisions**: a "Bias mitigation" section was deferred to Phase 1.5; the
README was written assuming Phase 1.5 would land soon.

### Phase 1.5 — Bias mitigation (commits `1fbc64c`, `65b023e`, `cb5cead`)

**Goal**: Move the model from "blocked by the gate" to "passes industry
gates".

**Approach**:
1. **Drop AGE numeric from training features** —
   `feature_engineering.excluded_features: [AGE]` in `params.yaml`.
   Forces the model to use behaviour signals (PAY_X, BILL_AMT) rather
   than the demographic shortcut.
2. **Kamiran-Calders sample reweighing** on AGE_BIN —
   `src/models/reweighing.py` implements
   `w(s, y) = P(s)·P(y) / P(s, y)`, passed as `sample_weight` to LightGBM
   in CV folds **and** the final fit. Balances outcome prevalence across
   age bands so equal-opportunity disparity shrinks.

**Tools**: `fairlearn` (for the metrics, not for the mitigation — the
reweighing is custom because Fairlearn doesn't ship Kamiran-Calders
directly).

**Tried + parked**: composite (AGE_BIN × EDUCATION) reweighing. The
EDUCATION subgroup 4 has only ~0.5% of rows; composite reweighing
amplified extreme weights and *slightly worsened* EDUCATION EOD. The code
supports `sensitive_attributes: [list]` so re-enabling is a one-line
config flip.

**Results**:

| Metric | v1 baseline | v2 Phase 1.5 | Production gate | Pass? |
| --- | --- | --- | --- | --- |
| AUC | 0.7532 | 0.7456 | ≥ 0.74 | ✓ |
| AGE_BIN EOD | 0.318 | **0.157** | ≤ 0.20 | ✓ |
| AGE_BIN DPD | 0.095 | 0.079 | ≤ 0.10 | ✓ |
| EDUCATION EOD | 0.196 | 0.198 | ≤ 0.20 | ✓ |
| EDUCATION DPD | 0.109 | 0.090 | ≤ 0.10 | ✓ |
| SEX EOD | 0.013 | 0.038 | ≤ 0.20 | ✓ |

**Production gates** were set at industry-aligned levels: DPD ≤ 0.10 (the
regulatory **80% rule** for disparate impact), EOD ≤ 0.20 (accommodates
structural prevalence differences). Tighter gates would require Fairlearn's
`ThresholdOptimizer` post-processing — documented as next-iteration work.

**Verification**: v2 model registered with `staging` alias; 6 new unit
tests on `reweighing.py` pass (balanced inputs → unit weights; skewed →
compensating; post-weight joint factorises; composite cells; length
mismatch raises; missing sensitive raises).

---

## Tech inventory

Every tool that earns a line in this project, what it does, where it
lives.

| Category | Tool | Where |
| --- | --- | --- |
| Lang / runtime | Python 3.11–3.13 | `pyproject.toml` |
| Build / deps | `setuptools`, editable install with extras | `pyproject.toml` |
| Data versioning | DVC + DVC-S3 | `dvc.yaml`, `params.yaml`, [`infra/s3.tf`](infra/s3.tf) |
| Data validation | Pandera | [`src/data/schemas.py`](src/data/schemas.py), [`src/data/validate.py`](src/data/validate.py) |
| Tabular ML | LightGBM (primary), XGBoost (alt) | [`src/models/train.py`](src/models/train.py) |
| HPO | Optuna with TPE sampler + median pruner | [`src/models/train.py`](src/models/train.py) |
| Experiment tracking | MLflow | [`src/models/{train,evaluate,register}.py`](src/models/) |
| Model registry | MLflow Registry with `staging` alias | [`src/models/register.py`](src/models/register.py) |
| Fairness metrics | Fairlearn (DPD, EOD, MetricFrame) | [`src/models/fairness.py`](src/models/fairness.py) |
| Bias mitigation | Custom Kamiran-Calders reweighing | [`src/models/reweighing.py`](src/models/reweighing.py) |
| Explainability | SHAP TreeExplainer | [`src/models/explain.py`](src/models/explain.py) |
| API serving | FastAPI + Uvicorn + Gunicorn | [`src/serving/app.py`](src/serving/app.py) |
| Schema validation | Pydantic v2 | [`src/serving/schemas.py`](src/serving/schemas.py) |
| Metrics | `prometheus_client` | [`src/serving/metrics.py`](src/serving/metrics.py) |
| Structured logs | `structlog` (JSON in prod, console in TTY) | [`src/utils.py`](src/utils.py) |
| Containerisation | Docker BuildKit + multi-stage build | [`docker/Dockerfile.api`](docker/Dockerfile.api) |
| Local stack | docker-compose with `full` profile (MLflow + Postgres + MinIO) | [`docker/docker-compose.yml`](docker/docker-compose.yml) |
| CI | GitHub Actions (lint/test/security/build) | [`.github/workflows/`](.github/workflows/) |
| CI mirror | Jenkins declarative pipeline | [`Jenkinsfile`](Jenkinsfile) |
| Image registry | GHCR | `ghcr.io/jayaram9196/mlops-credit-default-platform` |
| Security scanning | Bandit (Python), Trivy (fs + image) | [`.github/workflows/ci.yml`](.github/workflows/ci.yml) |
| Kubernetes | Helm chart (Deployment / Rollout / HPA / PDB / NetworkPolicy / ServiceMonitor / CronJob) | [`k8s/helm/credit-default-api/`](k8s/helm/credit-default-api/) |
| GitOps | Argo CD Application | [`k8s/argocd-application.yaml`](k8s/argocd-application.yaml) |
| Canary | Argo Rollouts + AnalysisTemplate (Prometheus checks) | [`k8s/helm/credit-default-api/templates/rollout.yaml`](k8s/helm/credit-default-api/templates/rollout.yaml) |
| IaC | Terraform 1.6+, `hashicorp/aws@~> 5.70` | [`infra/`](infra/) |
| Network | `terraform-aws-modules/vpc/aws` | [`infra/vpc.tf`](infra/vpc.tf) |
| Compute | `terraform-aws-modules/eks/aws` | [`infra/eks.tf`](infra/eks.tf) |
| Image hosting | AWS ECR (IMMUTABLE, scan-on-push) | [`infra/ecr.tf`](infra/ecr.tf) |
| Object storage | S3 with versioning + SSE + lifecycle | [`infra/s3.tf`](infra/s3.tf) |
| Identity | IAM with IRSA + GitHub OIDC deploy role | [`infra/iam.tf`](infra/iam.tf) |
| Training | SageMaker (alternate path) | [`infra/sagemaker.tf`](infra/sagemaker.tf) |
| Batch scoring | Lambda triggered by S3 events | [`infra/lambda.tf`](infra/lambda.tf), [`infra/lambda/scorer.py`](infra/lambda/scorer.py) |
| Log aggregation | CloudWatch log groups + metric filter + alarm | [`infra/cloudwatch.tf`](infra/cloudwatch.tf) |
| State backend | S3 + DynamoDB lock (bootstrap stack) | [`infra/bootstrap/`](infra/bootstrap/) |
| Monitoring | Prometheus + Alertmanager + Grafana | [`monitoring/`](monitoring/) |
| Drift detection | Evidently AI `DataDriftPreset` | [`src/monitoring/drift.py`](src/monitoring/drift.py) |
| Orchestration | Apache Airflow 2.9+ DAG | [`airflow/dags/credit_default_retrain.py`](airflow/dags/credit_default_retrain.py) |
| Alt orchestration | AWS Step Functions ASL | [`pipelines/step-functions/retrain.asl.json`](pipelines/step-functions/retrain.asl.json) |
| LLM | LangChain (`fake` / OpenAI / Bedrock providers) | [`src/llm/explainer.py`](src/llm/explainer.py) |
| Vector store | FAISS + `sentence-transformers/all-MiniLM-L6-v2` | [`src/llm/vectorstore.py`](src/llm/vectorstore.py) |
| Test runner | pytest + pytest-cov | [`pyproject.toml`](pyproject.toml), [`tests/`](tests/) |
| Load testing | locust (dev extra) | `pyproject.toml.dev` |
| Linting | ruff, black, mypy, bandit, pre-commit | [`pyproject.toml`](pyproject.toml), [`.pre-commit-config.yaml`](.pre-commit-config.yaml) |

---

## Numbers worth quoting

- **34 tests passing**: 21 base unit + 6 reweighing unit + 7 integration.
- **AUC 0.7456 / KS 0.385 / Lift@10% 2.92** on the holdout, v2.
- **AGE-band equal-opportunity disparity cut by 50%** (0.318 → 0.157) for
  an AUC cost of 0.7 points.
- **p95 prediction latency < 200 ms** in the containerised stack (cold).
- **16 commits** total across 12 days of work.
- **~6,500 lines of code** across 90+ files.
- **CI runtime ~6–8 minutes per PR**; build-deploy ~10–12 min.

---

## Lessons learned

Things that turned out non-obvious or expensive.

1. **Data plumbing eats the most time.** Dataset pivot (Kaggle → UCI →
   OpenML), the UCI TLS cert expiring, the disk-space crash, and the
   Windows / OneDrive friction together cost more wall-clock than any
   single phase of code.
2. **Pickle module names matter.** A dataclass defined in a file run via
   `python -m foo` gets pickled with module = `__main__`. Move shared
   types into plain modules **or** use plain dicts.
3. **Trivy via the official install script is more robust than the
   `aquasecurity/trivy-action`** at least on Windows-hosted GHCR pulls and
   pinned tags. Removing the action dependency made the pipeline
   reproducible.
4. **`docker/metadata-action@v5.version` is not the SHA.** It's the first
   generated tag. For trivy / deploy commands, prefer the **digest** —
   `…@${{ steps.push.outputs.digest }}` is correct and immutable.
5. **Fairness gates that block a model are a feature.** The v1 model's
   gate failure became the most useful interview talking point: "the
   platform's automated gate detected a 32% equal-opportunity disparity
   and blocked promotion; here's how I dropped it 50% in v2."
6. **MLflow on Windows wants three slashes.** `file:///C:/...` not
   `file://C:/...`. Use `Path.as_uri()` not `f"file://{path.as_posix()}"`.
7. **Composite reweighing isn't always better.** AGE_BIN-only reweighing
   cleared the priority gap; adding EDUCATION made things worse because
   one subgroup (EDU=4) was too sparse to weight reliably.
8. **OneDrive on a project directory is fine for git and source but
   slow for `.venv` and Docker build contexts.** Trade off intentionally.

---

## Where to go next

| Next iteration | Why |
| --- | --- |
| Fairlearn `ThresholdOptimizer` post-processing | Drives EDUCATION EOD below 0.10. Requires sensitive features at inference time so the serving contract changes. |
| Bump `optuna_trials: 5 → 30+` for prod runs | The smoke value is leaving HPO performance on the table. CI keeps 5 for cycle-time. |
| MLflow file-store → SQLite backend | The deprecation warning is benign now but the path is documented. |
| Real EKS apply for demo screenshots, then destroy | The terraform code already validates clean; ~$2 for an afternoon's demo. |
| Loom demo video (~5 minutes) | Walkthrough = README architecture diagram → `dvc repro` running → MLflow UI → containerised `/predict` + `/explain/llm` → Grafana dashboards. |
| Drop EDUCATION subgroup 4 from training | ~120 rows of an "other" bucket may be costing more than it gives. Worth a quick A/B. |

---

## Document version

- **2026-05-25** — Initial draft after Phase 1.5 + trivy CI fix landed
  (commits `1fbc64c` → `cb5cead`).
