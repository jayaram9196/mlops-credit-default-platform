"""Register stage: gate by metrics + fairness, promote to MLflow Registry.

Promotion rule:
- holdout AUC >= min_auc_for_promotion
- for every protected attribute scored: |demographic_parity_diff| and
  |equal_opportunity_diff| within the configured thresholds.

If all gates pass the model is logged with `mlflow.sklearn.log_model`, registered
under `registered_model_name`, and tagged with the staging alias.
"""

from __future__ import annotations

import json
import sys

import joblib
import mlflow
import mlflow.sklearn
from mlflow import MlflowClient

from src.utils import configure_logging, get_logger, load_params, project_path

log = get_logger(__name__)


def passes_gates(metrics: dict, eval_cfg: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if metrics["auc"] < eval_cfg["min_auc_for_promotion"]:
        reasons.append(
            f"AUC {metrics['auc']:.4f} below threshold {eval_cfg['min_auc_for_promotion']}"
        )
    for f in metrics.get("fairness", []):
        if abs(f["demographic_parity_diff"]) > eval_cfg["max_demographic_parity_diff"]:
            reasons.append(
                f"demographic_parity_diff[{f['attribute']}]={f['demographic_parity_diff']:.3f} "
                f"exceeds {eval_cfg['max_demographic_parity_diff']}"
            )
        if abs(f["equal_opportunity_diff"]) > eval_cfg["max_equal_opportunity_diff"]:
            reasons.append(
                f"equal_opportunity_diff[{f['attribute']}]={f['equal_opportunity_diff']:.3f} "
                f"exceeds {eval_cfg['max_equal_opportunity_diff']}"
            )
    return (len(reasons) == 0, reasons)


def main() -> int:
    configure_logging()
    params = load_params()
    eval_cfg = params["model_evaluation"]
    reg_cfg = params["model_registration"]

    metrics_path = project_path("reports/metrics.json")
    metrics = json.loads(metrics_path.read_text())

    ok, reasons = passes_gates(metrics, eval_cfg)
    if not ok:
        log.error("register.gate.fail", reasons=reasons)
        return 2

    mlflow.set_tracking_uri(project_path("mlruns").as_uri())
    mlflow.set_experiment(reg_cfg["mlflow_experiment"])

    bundle = joblib.load(project_path("models/model.joblib"))
    model = bundle["model"]
    feature_names = bundle["feature_names"]

    with mlflow.start_run(run_name="register") as run:
        mlflow.log_metrics(
            {
                "holdout_auc": float(metrics["auc"]),
                "holdout_ks": float(metrics["ks"]),
            }
        )
        mlflow.log_dict({"feature_names": feature_names}, "feature_names.json")
        model_info = mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path="model",
            registered_model_name=reg_cfg["registered_model_name"],
        )
        mlflow.set_tag("phase", "register")

        client = MlflowClient()
        version = model_info.registered_model_version
        client.set_registered_model_alias(
            name=reg_cfg["registered_model_name"],
            alias=reg_cfg["staging_alias"],
            version=version,
        )
        log.info(
            "register.done",
            model=reg_cfg["registered_model_name"],
            version=version,
            alias=reg_cfg["staging_alias"],
            run_id=run.info.run_id,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
