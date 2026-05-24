"""SHAP-based explainability — global summary plot and per-instance attributions.

The per-instance helper is reused by the serving layer in Phase 2.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # non-interactive backend, safe inside DVC stages
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap


def build_tree_explainer(model) -> shap.TreeExplainer:
    return shap.TreeExplainer(model)


def global_summary_plot(
    explainer: shap.TreeExplainer,
    X: pd.DataFrame,
    out_path: Path,
    max_display: int = 20,
    sample_size: int = 2000,
) -> None:
    sample = X.sample(min(sample_size, len(X)), random_state=42) if len(X) > sample_size else X
    shap_values = explainer.shap_values(sample)
    plt.figure(figsize=(10, 7))
    shap.summary_plot(
        shap_values,
        sample,
        max_display=max_display,
        show=False,
    )
    plt.tight_layout()
    plt.savefig(out_path, dpi=110, bbox_inches="tight")
    plt.close()


def top_drivers_for_instance(
    explainer: shap.TreeExplainer,
    x: pd.DataFrame | np.ndarray,
    feature_names: list[str],
    k: int = 5,
) -> list[dict]:
    """Return the top-k (by absolute SHAP value) feature contributions for one row."""
    sv = explainer.shap_values(x)
    if isinstance(sv, list):  # binary classification can return list of arrays
        sv = sv[1] if len(sv) == 2 else sv[0]
    sv = np.asarray(sv).reshape(-1)
    order = np.argsort(-np.abs(sv))[:k]
    return [
        {"feature": feature_names[i], "shap_value": float(sv[i])}
        for i in order
    ]
