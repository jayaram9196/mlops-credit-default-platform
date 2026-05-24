"""Fairness metrics using fairlearn — demographic parity + equal opportunity.

Used by the evaluate stage as a gate before model registration.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from fairlearn.metrics import (
    MetricFrame,
    demographic_parity_difference,
    equalized_odds_difference,
    true_positive_rate,
)
from sklearn.metrics import roc_auc_score


@dataclass
class FairnessResult:
    attribute: str
    demographic_parity_diff: float
    equal_opportunity_diff: float
    auc_by_group: dict[str, float]
    tpr_by_group: dict[str, float]
    selection_rate_by_group: dict[str, float]


def _selection_rate(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(y_pred))


def compute_fairness(
    y_true: np.ndarray,
    y_score: np.ndarray,
    sensitive: pd.Series,
    threshold: float = 0.5,
) -> FairnessResult:
    y_pred = (y_score >= threshold).astype(int)

    dp = demographic_parity_difference(y_true, y_pred, sensitive_features=sensitive)
    eo = equalized_odds_difference(y_true, y_pred, sensitive_features=sensitive)

    by_group_auc = (
        MetricFrame(
            metrics={"auc": roc_auc_score},
            y_true=y_true,
            y_pred=y_score,
            sensitive_features=sensitive,
        )
        .by_group["auc"]
        .to_dict()
    )

    by_group_tpr = (
        MetricFrame(
            metrics={"tpr": true_positive_rate},
            y_true=y_true,
            y_pred=y_pred,
            sensitive_features=sensitive,
        )
        .by_group["tpr"]
        .to_dict()
    )

    by_group_sel = (
        MetricFrame(
            metrics={"sel": _selection_rate},
            y_true=y_true,
            y_pred=y_pred,
            sensitive_features=sensitive,
        )
        .by_group["sel"]
        .to_dict()
    )

    return FairnessResult(
        attribute=sensitive.name or "",
        demographic_parity_diff=float(dp),
        equal_opportunity_diff=float(eo),
        auc_by_group={str(k): float(v) for k, v in by_group_auc.items()},
        tpr_by_group={str(k): float(v) for k, v in by_group_tpr.items()},
        selection_rate_by_group={str(k): float(v) for k, v in by_group_sel.items()},
    )


def fairness_to_dict(r: FairnessResult) -> dict:
    return {
        "attribute": r.attribute,
        "demographic_parity_diff": r.demographic_parity_diff,
        "equal_opportunity_diff": r.equal_opportunity_diff,
        "auc_by_group": r.auc_by_group,
        "tpr_by_group": r.tpr_by_group,
        "selection_rate_by_group": r.selection_rate_by_group,
    }
