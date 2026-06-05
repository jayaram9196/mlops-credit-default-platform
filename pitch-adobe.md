# MLOps & LLMOps Portfolio — Adobe AI Platform role

Two end-to-end projects, framed against the Adobe AI Platform job description.
The first is the substance; the second is the foundation it was built on.

## Credit Default Risk Platform — primary

Repo: https://github.com/jayaram9196/mlops-credit-default-platform

Production-grade MLOps platform on AWS. Trains a LightGBM credit-default
model on the UCI Taiwan dataset, serves it through a FastAPI container on
EKS with Argo Rollouts canary deploys, monitors data + concept drift with
Evidently, retrains weekly (or on drift) via an Apache Airflow DAG (AWS
Step Functions ASL alt), and explains every adverse decision with a
LangChain + FAISS RAG layer that refuses to cite protected attributes.

- Holdout AUC 0.7456 / KS 0.385 / Lift@10% 2.92 on the v2 model.
- AGE-band equal-opportunity disparity cut 50% (0.318 → 0.157) via
  Kamiran-Calders sample reweighing — for a 0.7-point AUC cost.
- p95 prediction latency < 200 ms in a non-root multi-stage Docker image.
- 34 tests passing; per-PR ruff / mypy / pytest / bandit / trivy in
  GitHub Actions + a Jenkinsfile mirror for Jenkins-first shops.
- Helm chart with HPA v2, PDB, NetworkPolicy, IRSA SA, ServiceMonitor.
- Argo Rollouts canary 10→25→50→100% guarded by Prometheus analysis
  on 5xx rate (<2%) and p95 latency (<500 ms).
- Terraform IaC: VPC, EKS, ECR, S3, IAM with IRSA + GitHub-OIDC deploy
  role, CloudWatch alarms, SageMaker training role, S3-triggered Lambda
  batch scorer. `terraform validate` clean.
- RAG explainer with a protected-attribute blocklist that refuses to
  cite SEX / AGE / MARRIAGE / EDUCATION even when SHAP attributes there.

## YouTube Sentiment Insights — foundation

First end-to-end MLOps project. LightGBM + TF-IDF (n-grams 1–3) sentiment
classifier; DVC pipeline → MLflow Registry → Flask REST API on AWS EC2 →
Chrome Manifest V3 extension that fetches YouTube comments and renders
sentiment breakdowns with word clouds. Established the DVC + MLflow + REST
pattern that the Credit Default Platform scaled to Kubernetes-native.

## Mapping to the Adobe AI Platform JD

| JD bullet | Where it lives |
| --- | --- |
| Scalable customer-facing AI platforms | FastAPI on EKS + Chrome plugin → Flask |
| ML pipelines (experiment / model / feature / retraining) | DVC + MLflow Registry + Airflow retrain DAG |
| A/B testing of models | Argo Rollouts canary with Prometheus AnalysisTemplate |
| Model-inference APIs at scale | FastAPI + HPA v2 + PDB on EKS |
| MLflow, SageMaker | Both used; SageMaker via Terraform + Step Functions |
| LLM serving + orchestration | LangChain LCEL + FAISS RAG; `/explain/llm` endpoint with guardrails |
| DevOps / LLMOps (K8s + Docker) | Helm chart, multi-stage Docker, Argo CD GitOps |
| Communication & articulation | Per-project README + IMPLEMENTATION_PLAN + WALKTHROUGH + resume |
| Continuous innovation / fail-fast | Phase 1.5 narrative: gate blocked v1, v2 cleared via reweighing |

## Honest gaps vs. the Adobe JD

GPU / distributed training: my LLM usage is via OpenAI / Bedrock APIs,
not self-hosted vLLM or DeepSpeed — onboarding ramp not core experience.
Vertex AI / Azure AI: the IaC is AWS-first; Azure ML would be a ~90-day
ramp. Flowise / Langflow / Langgraph specifically: I use LangChain LCEL
directly today, with a Langgraph rewrite of the explainer already on the
near-term roadmap.

## Already scoped as the next iteration

Fairlearn ThresholdOptimizer post-processing to drive EOD toward zero;
MLflow SQLite backend swap; a Langgraph rewrite of the RAG composer to
show stateful agent flow; a Loom demo walking through the architecture,
`/predict`, `/explain/llm`, and the Grafana dashboards.
