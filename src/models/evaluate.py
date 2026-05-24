"""Evaluate stage: score the trained model on the holdout split.

Outputs:
- reports/metrics.json   AUC, KS, lift, calibration error, fairness summary.
- reports/plots/*.png    ROC, calibration, SHAP summary, fairness bar.
- MLflow run             Logs metrics + plots as artifacts.

The metrics file is consumed by the register stage to decide promotion.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
    roc_curve,
)

from src.models.explain import build_tree_explainer, global_summary_plot
from src.models.fairness import compute_fairness, fairness_to_dict
from src.utils import configure_logging, ensure_dir, get_logger, load_params, project_path

log = get_logger(__name__)
TARGET = "TARGET"


def ks_statistic(y_true: np.ndarray, y_score: np.ndarray) -> float:
    pos = y_score[y_true == 1]
    neg = y_score[y_true == 0]
    thresholds = np.linspace(0, 1, 101)
    tpr = np.array([(pos >= t).mean() for t in thresholds])
    fpr = np.array([(neg >= t).mean() for t in thresholds])
    return float(np.max(np.abs(tpr - fpr)))


def lift_at_top_decile(y_true: np.ndarray, y_score: np.ndarray) -> float:
    n = len(y_true)
    k = max(1, n // 10)
    top = np.argsort(-y_score)[:k]
    base_rate = y_true.mean()
    if base_rate == 0:
        return 0.0
    return float(y_true[top].mean() / base_rate)


def plot_roc(y_true: np.ndarray, y_score: np.ndarray, out_path: Path) -> None:
    fpr, tpr, _ = roc_curve(y_true, y_score)
    auc = roc_auc_score(y_true, y_score)
    plt.figure(figsize=(6, 6))
    plt.plot(fpr, tpr, label=f"AUC = {auc:.3f}")
    plt.plot([0, 1], [0, 1], "k--", alpha=0.5)
    plt.xlabel("False positive rate")
    plt.ylabel("True positive rate")
    plt.title("ROC curve — holdout")
    plt.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(out_path, dpi=110)
    plt.close()


def plot_calibration(y_true: np.ndarray, y_score: np.ndarray, out_path: Path) -> None:
    prob_true, prob_pred = calibration_curve(y_true, y_score, n_bins=10, strategy="quantile")
    plt.figure(figsize=(6, 6))
    plt.plot(prob_pred, prob_true, marker="o", label="model")
    plt.plot([0, 1], [0, 1], "k--", alpha=0.5, label="perfect")
    plt.xlabel("Mean predicted probability")
    plt.ylabel("Fraction of positives")
    plt.title("Calibration — holdout")
    plt.legend(loc="upper left")
    plt.tight_layout()
    plt.savefig(out_path, dpi=110)
    plt.close()


def main() -> int:
    configure_logging()
    params = load_params()
    eval_cfg = params["model_evaluation"]
    reg_cfg = params["model_registration"]

    processed = project_path("data/processed")
    models_dir = project_path("models")
    reports_dir = ensure_dir(project_path("reports"))
    plots_dir = ensure_dir(project_path("reports/plots"))

    bundle = joblib.load(models_dir / "model.joblib")
    model = bundle["model"]
    feature_names: list[str] = bundle["feature_names"]

    df = pd.read_parquet(processed / "holdout.parquet")
    y = df[TARGET].astype(int).to_numpy()
    drop = [TARGET, "SEX", "EDUCATION", "MARRIAGE", "AGE_BIN"]
    X = df.drop(columns=[c for c in drop if c in df.columns])
    X = X[feature_names]

    y_score = model.predict_proba(X)[:, 1]

    auc = float(roc_auc_score(y, y_score))
    pr_auc = float(average_precision_score(y, y_score))
    ks = ks_statistic(y, y_score)
    lift10 = lift_at_top_decile(y, y_score)
    brier = float(brier_score_loss(y, y_score))

    plot_roc(y, y_score, plots_dir / "roc_curve.png")
    plot_calibration(y, y_score, plots_dir / "calibration.png")

    explainer = build_tree_explainer(model)
    global_summary_plot(explainer, X, plots_dir / "shap_summary.png")

    fairness: list[dict] = []
    for attr in eval_cfg["protected_attributes"]:
        if attr not in df.columns:
            log.warning("evaluate.fairness.skip", attribute=attr, reason="missing column")
            continue
        sensitive = df[attr].astype("string").fillna("unknown")
        sensitive.name = attr
        result = compute_fairness(y, y_score, sensitive)
        fairness.append(fairness_to_dict(result))

    metrics = {
        "auc": auc,
        "pr_auc": pr_auc,
        "ks": ks,
        "lift_top_decile": lift10,
        "brier": brier,
        "fairness": fairness,
        "thresholds": {
            "min_auc": eval_cfg["min_auc_for_promotion"],
            "max_demographic_parity_diff": eval_cfg["max_demographic_parity_diff"],
            "max_equal_opportunity_diff": eval_cfg["max_equal_opportunity_diff"],
        },
    }
    metrics_path = reports_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2))

    mlflow.set_tracking_uri(project_path("mlruns").as_uri())
    mlflow.set_experiment(reg_cfg["mlflow_experiment"])
    with mlflow.start_run(run_name="evaluate"):
        mlflow.log_metrics({"holdout_auc": auc, "holdout_ks": ks, "holdout_pr_auc": pr_auc,
                            "holdout_lift10": lift10, "holdout_brier": brier})
        for f in fairness:
            mlflow.log_metric(f"dpd_{f['attribute']}", f["demographic_parity_diff"])
            mlflow.log_metric(f"eod_{f['attribute']}", f["equal_opportunity_diff"])
        for png in plots_dir.glob("*.png"):
            mlflow.log_artifact(str(png), artifact_path="plots")
        mlflow.log_artifact(str(metrics_path))

    log.info("evaluate.done", auc=auc, ks=ks, lift10=lift10, fairness_attrs=len(fairness))
    return 0


if __name__ == "__main__":
    sys.exit(main())
