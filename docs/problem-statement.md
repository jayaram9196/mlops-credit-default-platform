# Problem Statement — Loan Default Risk

## Context

A consumer lender receives loan applications and must decide, within seconds, whether to approve, reject, or send the application to manual underwriting. Mis-classifying a defaulter as a good borrower causes direct loss; mis-classifying a good borrower as a defaulter causes lost revenue and customer-acquisition cost.

The lender operates in a regulated jurisdiction. Every adverse decision must be explainable to the applicant and auditable by regulators. Decisions cannot rely on protected attributes (gender, age, etc.) and must demonstrate that disparity across protected groups stays within agreed thresholds.

## Objective

Build a platform that:

1. Trains a model to predict probability of default `P(default | applicant)` from the UCI Default of Credit Card Clients (Taiwan) dataset.
2. Serves predictions in real time (single applicant) and in batch (overnight portfolio scoring).
3. Produces, for every adverse prediction, a plain-English explanation citing the policy or feature drivers that led to the decision.
4. Continuously monitors data + prediction drift and retrains automatically when drift exceeds thresholds.

## Non-functional requirements

| Concern | Target |
| --- | --- |
| Real-time p95 latency | < 150 ms |
| Real-time availability | 99.5% |
| Batch throughput | 100K applications / hour |
| Retraining cadence | weekly schedule + drift-triggered |
| Time to detect drift | < 24 h |
| Time to roll back a bad deploy | < 5 min |
| Audit log retention | 90 days hot, 7 yrs cold |

## Success metrics

**Model.**
- AUC ≥ 0.74 on hold-out (typical LightGBM ceiling on this dataset is ~0.78–0.80).
- KS statistic ≥ 0.30.
- Demographic-parity difference ≤ 0.05 across `CODE_GENDER` and age bins.
- Equal-opportunity difference ≤ 0.05.

**Platform.**
- Deployment frequency: ≥ 1 / week on main.
- Change failure rate: ≤ 10%.
- MTTR (model rollback): ≤ 5 min.

## Out of scope

- Loan pricing / interest-rate optimisation.
- Fraud detection (separate model).
- KYC / identity verification.
- Production-grade A/B testing framework (only canary rollout is in scope).

## Data

**Source.** UCI Machine Learning Repository — [Default of Credit Card Clients](https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients) (Taiwan, 2005). Fetched via the `ucimlrepo` Python package (no auth, public download). 30,000 rows; one row per cardholder.

**Columns (selected).**
- `LIMIT_BAL` — credit limit (NT dollars).
- `SEX`, `EDUCATION`, `MARRIAGE` — demographics (also used as protected attributes for fairness analysis).
- `AGE` — years (also bucketed into `AGE_BIN`).
- `PAY_0, PAY_2…PAY_6` — repayment status for the most recent six monthly statements (-2 = no consumption, -1 = paid in full, 0 = revolving credit, 1…9 = months past due).
- `BILL_AMT1…BILL_AMT6` — bill amount per month.
- `PAY_AMT1…PAY_AMT6` — payment made per month.
- `TARGET` — 1 if the cardholder defaulted on the next month's payment.

**Protected attributes for fairness analysis.** `SEX`, derived `AGE_BIN`, `EDUCATION`.

**Why this dataset.** Real lender repayment data; matches the regulated-credit-risk framing; the multi-month time-series columns reward proper window-aggregation feature engineering; small enough (30K rows) to iterate quickly on a laptop but realistic enough to discuss in interviews.

## Architecture (high level)

See [architecture.md](architecture.md). The platform is a set of containerised services running on Kubernetes, fronted by an API gateway, with a model registry, feature pipeline, monitoring stack, and orchestration layer.
