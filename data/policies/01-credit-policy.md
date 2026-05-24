---
policy_id: CP-01
section: "1.1 — Underwriting thresholds"
last_reviewed: 2026-04-01
owner: Credit Risk
---

# Credit Policy — Underwriting Thresholds

## 1.1 Decision matrix

The lender approves applications that meet **all** of the following criteria:

- Debt-to-income (DTI) ratio at or below **36%**. Applications with DTI between
  36% and 43% may be approved subject to compensating factors (see §1.4).
- Credit history of **24 months or longer**. Files with shorter credit history
  may proceed only through manual underwriting.
- A maximum of **three** delinquency events of any size in the trailing six
  months (the trailing-six `PAY_X` columns).
- Credit utilisation on revolving accounts of **less than 70%** at application
  time.

## 1.2 Automated denial

The application is automatically denied when:

- Two or more 60+-day delinquencies are observed in the trailing six months.
- The applicant has filed for bankruptcy within 24 months.
- Utilisation exceeds 100% (over-limit on revolving accounts).

## 1.3 Manual review triggers

The platform marks an application for manual review when the automated score
falls into the **review** decision band (P(default) between 0.30 and 0.60),
where adverse-action notice obligations require a human reviewer to confirm
the reasons before issuing the decision.
