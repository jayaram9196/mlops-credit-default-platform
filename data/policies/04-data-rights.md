---
policy_id: DR-01
section: "4.1 — Data subject rights"
last_reviewed: 2026-04-01
owner: Privacy
---

# Data Rights — Predictions and Automated Decisions

## 4.1 Right to explanation

Under GDPR Article 22 and similar regulation, applicants subject to a fully
**automated** decision have the right to:

- Obtain meaningful information about the logic involved.
- Request human review of the decision.
- Contest the decision and have it reconsidered.

The `/explain/llm` endpoint exists to satisfy the first requirement. It
combines per-prediction SHAP attribution with a retrieval over this policy
corpus to produce a natural-language explanation grounded in cited policy
sections.

## 4.2 Audit trail

Each prediction is logged with the model version, request id, top-K SHAP
drivers, decision, and the policy sections cited in the explanation. The audit
log is retained for **seven years** in hot storage for the first 90 days and
S3 Glacier thereafter.

## 4.3 Right to deletion

Applicants may request deletion of their submitted data. Deletion removes
the raw application from `s3://<data>/raw/` but retains the **prediction
record** (without the application payload) for regulatory traceability.
