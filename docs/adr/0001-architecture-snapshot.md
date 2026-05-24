# ADR 0001 — Initial architecture snapshot

**Status:** Accepted
**Date:** 2026-05-24

## Context

Need to decide a default tech stack for the loan-default platform before starting Phase 1. The constraint is to maximise coverage of MLOps job-description bullets while staying buildable by a single engineer in ~10 weeks part-time.

## Decision

- **Cloud:** AWS primary. Azure equivalents documented later if a JD specifically demands it. Reason: TCS + JD#1 are AWS-heavy, and AWS has the broadest MLOps tooling story (SageMaker, Bedrock, EKS, Lambda).
- **Spend strategy:** Local-first using kind/minikube for K8s and minio/postgres for storage and MLflow backend. Terraform code written so a real EKS environment can be spun up for demo screenshots, then destroyed. Reason: optimise for code quality over actual cloud bill; recruiters review repos, not invoices.
- **Dataset:** UCI Default of Credit Card Clients (Taiwan, id=350) via `ucimlrepo`. Reason: real lender repayment data, no auth/verification friction, explicit protected attributes (SEX/AGE/EDUCATION/MARRIAGE) make the fairness story richer than Home Credit. Pivoted from Home Credit after Kaggle multi-account/phone-verify issues blocked competition-rule acceptance.
- **ML framework:** LightGBM as primary baseline, XGBoost as alternative, both via Optuna for HPO. Reason: SOTA on tabular, well-understood, deploys easily.
- **Serving:** FastAPI (not Flask). Reason: modern, async-capable, OpenAPI docs free, better story than Flask.
- **Experiment tracking + registry:** MLflow. Reason: explicitly named in JD#1.
- **CI/CD:** GitHub Actions primary, Jenkinsfile mirror. Reason: GH Actions is industry default; Jenkinsfile addresses TCS's Jenkins ask.
- **K8s:** vanilla manifests then Helm chart. Argo CD optional. Reason: portable across EKS/AKS/GKE.
- **Monitoring:** Prometheus + Grafana for ops, Evidently for drift. Reason: open-source, well-known, easy to demo locally.
- **LLM:** LangChain + FAISS local, Bedrock or OpenAI for hosted inference. Reason: covers Salesforce + Bell Techlogix LLM bullets.

## Consequences

- We accept a one-cloud bias (AWS). If a target role is Azure-only (e.g., Bell Techlogix), we'll add an Azure ADR + parallel Terraform/Bicep variant in Phase 5.
- Local-first means some screenshots will be from kind, not EKS. We'll mitigate by spinning up real EKS at the end for demo media before submitting applications.
- Choosing FastAPI over Flask diverges from the older `yts_insights` project — intentional.
