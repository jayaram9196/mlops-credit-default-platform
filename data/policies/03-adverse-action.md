---
policy_id: AA-01
section: "3.1 — Adverse action notice"
last_reviewed: 2026-04-01
owner: Compliance
---

# Adverse Action — Notice Requirements

## 3.1 Triggers

The Fair Credit Reporting Act (FCRA) requires the lender to issue an adverse
action notice whenever an application is **denied** or approved on **less
favourable terms** than requested. The notice must include:

- The principal reasons (up to four) for the adverse decision.
- The contact information of any consumer reporting agency whose data was used.
- The applicant's right to obtain a free copy of the credit report and to
  dispute its accuracy.

## 3.2 Reason ordering

When the explanation service surfaces SHAP drivers, the top-K drivers are
re-ordered to comply with the **most-material-first** rule: reasons must be
listed in descending order of contribution magnitude, **excluding** any
protected-class features per §2 (Fair Lending).

## 3.3 Plain-language requirement

Each cited reason must be paraphrased in plain language understandable to a
non-technical applicant. Example translations:

| Feature | Plain language |
| --- | --- |
| `PAY_DELAY_MAX` ≥ 2 | "Your record shows at least one payment 60 or more days past due in the last six months." |
| `UTILISATION_LAST` > 0.7 | "Your current balance on revolving accounts exceeds 70% of your credit limit." |
| `PAY_DELAY_COUNT` ≥ 3 | "Multiple delinquency events have been reported in the last six months." |
| `BILL_TREND` strongly positive | "Bill balances have been rising consistently over the last six months." |
