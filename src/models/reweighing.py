"""Kamiran & Calders (2012) reweighing.

Returns sample weights so that, after weighting, the joint distribution
P(Y, S) factorises as the product of marginals P(Y) * P(S). This counteracts
the prevalence skew across subgroups that drives equal-opportunity disparity.

Supports one or more sensitive attributes: with multiple, the cells are the
cartesian product of categories (e.g. AGE_BIN x EDUCATION).

Reference:
    Kamiran, F., Calders, T. (2012). "Data preprocessing techniques for
    classification without discrimination." Knowledge and Information Systems.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _composite(sensitives: tuple[pd.Series, ...]) -> pd.Series:
    if not sensitives:
        raise ValueError("at least one sensitive attribute is required")
    parts = [s.astype("string").fillna("unknown").reset_index(drop=True) for s in sensitives]
    composite = parts[0]
    for p in parts[1:]:
        composite = composite.str.cat(p, sep="|")
    return composite


def compute_weights(y: pd.Series, *sensitives: pd.Series) -> np.ndarray:
    """Per-sample weights such that w[i] = P(Y=y_i) * P(S=s_i) / P(Y=y_i, S=s_i)."""
    for s in sensitives:
        if len(s) != len(y):
            raise ValueError("each sensitive attribute must be the same length as y")

    sensitive = _composite(sensitives)
    y = y.reset_index(drop=True).astype(int)

    n = len(y)
    weights = np.ones(n, dtype=float)

    for s_val in sensitive.unique():
        for y_val in (0, 1):
            mask = (sensitive == s_val).to_numpy() & (y == y_val).to_numpy()
            n_observed = int(mask.sum())
            if n_observed == 0:
                continue
            p_y = float((y == y_val).mean())
            p_s = float((sensitive == s_val).mean())
            n_expected = p_y * p_s * n
            weights[mask] = n_expected / n_observed

    return weights


def weight_summary(weights: np.ndarray, y: pd.Series, *sensitives: pd.Series) -> pd.DataFrame:
    """Per-cell summary of pre/post-weight proportions for the audit trail."""
    sensitive = _composite(sensitives)
    y = y.reset_index(drop=True).astype(int)
    rows = []
    n = len(y)
    total_weight = float(weights.sum()) or 1.0
    for s_val in sorted(sensitive.unique()):
        for y_val in (0, 1):
            mask = (sensitive == s_val).to_numpy() & (y == y_val).to_numpy()
            count = int(mask.sum())
            if count == 0:
                continue
            rows.append(
                {
                    "sensitive": s_val,
                    "target": y_val,
                    "count": count,
                    "raw_share": count / n,
                    "weight_share": float(weights[mask].sum()) / total_weight,
                    "mean_weight": float(weights[mask].mean()),
                }
            )
    return pd.DataFrame(rows)
