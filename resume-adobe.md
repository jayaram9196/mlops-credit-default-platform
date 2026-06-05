# Mudigonda Venkata Gopi Jayaram

mvenkatagopi2000@gmail.com | 9390682953
linkedin.com/in/mudigonda-venkata-gopi-jayaram-519715216
github.com/jayaram9196

## Profile

AI Engineer with ~3 years of experience designing and deploying scalable,
customer-facing Generative AI platforms and end-to-end MLOps pipelines.
Specialised in Retrieval-Augmented Generation (RAG), Agentic AI, multi-agent
orchestration with LangGraph and CrewAI, and production LLMOps on AWS.
Hands-on experience with the full ML lifecycle: experiment tracking,
model registry, feature pipelines, drift-triggered retraining, A/B testing
via canary deploys, and inference APIs at scale. Strong record of shipping
secure, observable, Responsible-AI-compliant GenAI services using FastAPI,
Docker, Kubernetes, Terraform, MLflow, and CI/CD on AWS.

## Skills

**Generative AI and Agentic Frameworks**
LangChain, LangGraph, CrewAI, Google ADK, OpenAI Agents SDK, Amazon Bedrock
Agents, RAG Pipelines, Multi-Agent Systems, Agentic Workflows, Prompt
Engineering, Function Calling, Structured Outputs, Model Context Protocol
(MCP), Guardrails

**LLMs and AI Platforms**
OpenAI GPT-4 / GPT-4o, Anthropic Claude, Google Gemini, Amazon Bedrock,
Meta Llama 3.x, Mistral, Embeddings, Token Optimization, Context
Management, LLM Serving Patterns

**Vector Databases and Retrieval**
Weaviate, ChromaDB, Pinecone, Redis Vector Search, FAISS, Hybrid Search
(BM25 + vector), Cross-Encoder Re-ranking, Semantic Search

**ML Pipelines and Experimentation**
MLflow Tracking and Model Registry, DVC, Optuna, scikit-learn, LightGBM,
XGBoost, SHAP, Fairlearn, Pandera, Great Expectations, A/B Testing,
Canary Deployments, Drift Detection (Evidently AI)

**Backend Development**
Python, FastAPI, AsyncIO, Pydantic v2, Flask, REST APIs, WebSockets,
PostgreSQL, SQL Optimization, Microservices Architecture

**Cloud and Infrastructure**
AWS (ECS, EKS, S3, RDS, DynamoDB, Lambda, API Gateway, OpenSearch,
CloudWatch, Step Functions, ECR, IAM with IRSA, SageMaker), Terraform,
Docker (multi-stage builds), Kubernetes (Helm, HPA, PDB, NetworkPolicy),
Argo Rollouts, Argo CD, Apache Airflow

**DevOps, MLOps, and LLMOps**
GitHub Actions, Jenkins, CI/CD, Infrastructure as Code (IaC), Git,
GitHub OIDC, Trivy, Bandit, pre-commit, container orchestration,
GitOps deployment patterns

**AI Evaluation and Observability**
LangSmith, RAGAS, LLM Evaluation Frameworks, Hallucination Detection,
AI Governance, Responsible AI, PII Protection, Prometheus, Grafana,
Alertmanager, structlog, OpenTelemetry-ready instrumentation

## Professional Experience

**Associate Engineer – Software Development, Virtusa Consulting Services** (Dec 2023 – Present)

- Designed and deployed an Enterprise GenAI Platform using FastAPI,
  Python, WebSockets, Docker, AWS ECS, and Terraform, enabling reusable
  AI services across multiple business units.
- Architected multi-agent AI workflows using LangGraph, CrewAI, and
  OpenAI Agents SDK with governance-aware orchestration and automated
  handoffs.
- Built production-grade RAG pipelines on Weaviate using hybrid retrieval,
  semantic search, and cross-encoder reranking, materially reducing
  hallucinations on enterprise document corpora.
- Developed automated LLM evaluation frameworks using SBERT, benchmark
  datasets, and regression testing in CI to ensure model quality and
  prevent quality regressions across releases.
- Implemented Responsible AI guardrails, PII protection, observability,
  and compliance controls for secure enterprise GenAI deployments.
- Automated infrastructure provisioning and deployments using AWS,
  Terraform, Docker, GitHub Actions, and CI/CD pipelines, including
  OIDC-keyless deploy roles for secret-free CI.
- Delivered reusable AI accelerators, internal productivity APIs, and
  shared evaluation harnesses that accelerated GenAI solution delivery
  across teams.

## Projects

**VisionNext Credit Genie** — Multi-agent conversational analytics on a credit-card data warehouse

- Designed a multi-agent system (orchestrator + SQL expert + visualiser)
  with a 6-layer grounded context pipeline and 4-layer guardrails
  (input/PII scrubbers, read-only SQL validator, token-budget gate) for
  safety and cost control.
- Shipped a two-tier semantic SQL cache (SHA + Redis cosine > 0.95)
  reducing repeat-query latency from 1.2 s to 150 ms.
- Built a deterministic eval harness (execution accuracy + sqlglot
  semantic equivalence) with a CI gate that blocks regressions.
- Deployed on AWS via Terraform (Aurora Serverless v2, ECS Fargate, ALB)
  with OIDC-keyless CI/CD and observability via LangSmith and Sentry.

**PE Document Intelligence Platform** — Multi-agent extraction over PE LPA and Subscription documents

- Built 6 specialised LangGraph subagents inside a bulk pipeline that
  processes 10 concurrent documents end-to-end.
- Designed the RAG stack with Weaviate hybrid search (BM25 + vector),
  cross-encoder re-ranking, and 2-stage markdown-aware chunking.
- Implemented structured extraction via dynamic Pydantic v2 models and a
  field-aware LLM-as-judge that scores per-field confidence.
- Shipped PII middleware that redacts SSN / email / phone / address
  before LLM calls while preserving 17 PE-domain financial terms.
- Contributed to a formal evals suite (classification, extraction, RAG,
  summarisation) inside a 511-test, 97%-coverage backend test base.

**Credit Default Risk Platform** — End-to-end MLOps on AWS (open-source portfolio)

Repo: github.com/jayaram9196/mlops-credit-default-platform

- Built a six-stage DVC pipeline (ingest → validate → features → train →
  evaluate → register) with LightGBM tuned via Optuna, MLflow nested
  runs for experiment tracking, and gated promotion to the Model
  Registry by AUC + Fairlearn fairness thresholds — holdout AUC 0.7456,
  KS 0.385, Lift@10% 2.92.
- Served the model via FastAPI (Pydantic v2 validation, SHAP `/explain`,
  Prometheus `/metrics`) at p95 < 200 ms in a non-root multi-stage Docker
  image, deployed on EKS through a Helm chart (HPA, PDB, NetworkPolicy,
  IRSA) with Argo Rollouts canary (10 → 25 → 50 → 100%) guarded by
  Prometheus AnalysisTemplate checks on 5xx rate and p95 latency for
  A/B-style rollouts.
- Shipped CI/CD in GitHub Actions and a mirrored Jenkinsfile — per-PR
  ruff, mypy, pytest, bandit, and trivy plus a `train` workflow that
  posts AUC + fairness diff back on the PR; on-merge build pushes to
  GHCR with sha + semver tags and runs a trivy image scan.
- Authored AWS infrastructure as Terraform (VPC, EKS, ECR, S3, IAM with
  IRSA + GitHub-OIDC deploy role, CloudWatch alarms, SageMaker training
  role, S3-triggered Lambda batch scorer); wired Evidently drift
  detection to a Kubernetes CronJob and added drift-triggered retraining
  via an Airflow DAG with an AWS Step Functions ASL alternative.
- Built an LLM/RAG explanation layer on LangChain + FAISS over a
  loan-policy corpus exposed via `/explain/llm`, with a protected-
  attribute blocklist that refuses to cite SEX / AGE / MARRIAGE /
  EDUCATION even when SHAP attributes there; reduced AGE-band equal-
  opportunity disparity 50% (0.318 → 0.157) via Kamiran-Calders sample
  reweighing for a 0.7-point AUC cost.

**YouTube Sentiment Insights** — Foundational MLOps + Chrome extension demo

- Trained a LightGBM + TF-IDF (n-grams 1–3) sentiment classifier with a
  reproducible DVC pipeline and MLflow Registry promotion to Staging.
- Served the model behind a Flask REST API on AWS EC2 with CORS-enabled
  endpoints and the exact preprocessing function reused from training to
  hold train/serve skew at zero.
- Built a Chrome Manifest V3 extension that fetches YouTube video comments
  via the YouTube Data API, batches them to the inference service, and
  renders sentiment breakdowns with on-demand word clouds — a live demo
  recruiters can install.

## Certifications

- AWS Certified AI Practitioner
- Google Cloud Certified Professional Machine Learning Engineer
- Google Cloud Certified Generative AI Leader
- Google Cloud Certified Associate Cloud Engineer
- Virtusa Certified Agentic AI Engineer
- Microsoft Certified Azure AI Fundamentals (AI-900)

## Education

**Bachelor of Technology, Computer Science and Engineering** (CGPA 8.43)
Vasireddy Venkatadri Institute of Technology, 2019 – 2023
