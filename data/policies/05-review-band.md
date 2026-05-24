---
policy_id: RB-01
section: "5.1 — Manual review band"
last_reviewed: 2026-04-01
owner: Underwriting
---

# Manual Review — When a Human Looks at It

## 5.1 Decision bands

The platform applies three decision bands keyed off the predicted P(default):

| P(default) | Decision | Action |
| --- | --- | --- |
| < 0.30 | approve | Auto-approved, audit-logged. |
| 0.30 – 0.60 | review | Forwarded to an underwriter within 24 hours. |
| ≥ 0.60 | deny | Auto-denied, FCRA adverse-action notice issued (§3). |

## 5.2 Underwriter information packet

Each application that enters the review band is forwarded to an underwriter
with:

- The full application payload as submitted.
- Top-5 SHAP drivers with feature-name and contribution magnitude.
- The natural-language explanation produced by `/explain/llm`.
- The list of policy sections cited.
- A flag indicating whether the application also tripped any §1.2 automatic
  denial rule (these should not reach the review band but may surface during
  policy mismatches).

## 5.3 Override authority

An underwriter may **approve** an application from the review band only when
the override is supported by a documented compensating factor under §1.4 of
the Credit Policy. Overrides toward **denial** require sign-off from a
second-line reviewer and are flagged for the model-fairness audit.
