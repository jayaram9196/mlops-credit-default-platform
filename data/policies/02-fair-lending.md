---
policy_id: FL-01
section: "2.1 — Protected-class neutrality"
last_reviewed: 2026-04-01
owner: Compliance
---

# Fair Lending — Equal Credit Opportunity

## 2.1 Protected attributes

Under ECOA (Equal Credit Opportunity Act, 15 U.S.C. §1691) and equivalent
local regulation, the following attributes **must not be used** as a decision
input nor cited as a driver of an adverse action:

- Gender / sex (`SEX` in the dataset)
- Age (`AGE`) above 18, where the applicant is legally capable of contracting
- Marital status (`MARRIAGE`)
- Race, religion, national origin, source of income from public assistance

## 2.2 Disparate impact thresholds

The platform monitors decision rates across protected attributes and rejects
the promotion of any model whose:

- **Demographic parity difference** exceeds **0.08** across `SEX`, `AGE` bands,
  or `MARRIAGE` categories.
- **Equal-opportunity difference** (true positive rate) exceeds **0.08**.

Phase 1's `register` stage applies these gates automatically and refuses to
promote a model that breaches them, regardless of headline AUC.

## 2.3 Explanation language

Any explanation surfaced to an applicant must cite **only features that are
legally permissible drivers** and must avoid suggesting that the decision
hinges on a protected attribute, even when SHAP attribution flags such a
feature. Wording must remain neutral and policy-grounded.
