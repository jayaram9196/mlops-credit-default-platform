"""Train stage: Optuna hyper-parameter search over LightGBM + MLflow tracking.

Each Optuna trial logs as a nested MLflow run. The final model is refit on the
full training split with the best params and persisted to `models/model.joblib`.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import joblib
import lightgbm as lgb
import mlflow
import numpy as np
import optuna
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

from src.utils import configure_logging, ensure_dir, get_logger, load_params, project_path

log = get_logger(__name__)
warnings.filterwarnings("ignore", category=UserWarning, module="lightgbm")

TARGET = "TARGET"


PROTECTED_COLUMNS = ["SEX", "EDUCATION", "MARRIAGE", "AGE_BIN"]


def load_train(path: Path) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    df = pd.read_parquet(path)
    y = df[TARGET].astype(int)
    drop = [TARGET, *PROTECTED_COLUMNS]
    feature_df = df.drop(columns=[c for c in drop if c in df.columns])
    protected = df[[c for c in PROTECTED_COLUMNS if c in df.columns]]
    return feature_df, y, protected


def cv_objective(
    trial: optuna.Trial,
    X: pd.DataFrame,
    y: pd.Series,
    base_params: dict,
    cv_folds: int,
    early_stopping_rounds: int,
    random_state: int,
) -> float:
    params = {
        **base_params,
        "num_leaves": trial.suggest_int("num_leaves", 16, 256),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        "feature_fraction": trial.suggest_float("feature_fraction", 0.5, 1.0),
        "bagging_fraction": trial.suggest_float("bagging_fraction", 0.5, 1.0),
        "bagging_freq": trial.suggest_int("bagging_freq", 0, 10),
        "min_child_samples": trial.suggest_int("min_child_samples", 5, 200),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10, log=True),
    }

    skf = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=random_state)
    aucs: list[float] = []
    for fold, (tr_idx, va_idx) in enumerate(skf.split(X, y)):
        X_tr, X_va = X.iloc[tr_idx], X.iloc[va_idx]
        y_tr, y_va = y.iloc[tr_idx], y.iloc[va_idx]

        model = lgb.LGBMClassifier(**params)
        model.fit(
            X_tr,
            y_tr,
            eval_set=[(X_va, y_va)],
            callbacks=[lgb.early_stopping(early_stopping_rounds, verbose=False)],
        )
        proba = model.predict_proba(X_va)[:, 1]
        auc = roc_auc_score(y_va, proba)
        aucs.append(auc)
        trial.report(auc, fold)
        if trial.should_prune():
            raise optuna.TrialPruned()

    mean_auc = float(np.mean(aucs))
    with mlflow.start_run(nested=True):
        mlflow.log_params(params)
        mlflow.log_metric("cv_auc_mean", mean_auc)
        mlflow.log_metric("cv_auc_std", float(np.std(aucs)))
    return mean_auc


def main() -> int:
    configure_logging()
    params = load_params()
    train_cfg = params["model_training"]
    lgbm_cfg = params["model_training_lightgbm"]
    reg_cfg = params["model_registration"]

    processed = project_path("data/processed")
    models_dir = ensure_dir(project_path("models"))
    reports_dir = ensure_dir(project_path("reports"))

    X, y, _ = load_train(processed / "train.parquet")
    log.info("train.data.loaded", rows=len(X), features=X.shape[1], default_rate=float(y.mean()))

    base_params = {
        "objective": "binary",
        "metric": "auc",
        "boosting_type": "gbdt",
        "n_estimators": lgbm_cfg["n_estimators"],
        "random_state": train_cfg["random_state"],
        "n_jobs": -1,
        "verbose": -1,
    }

    mlflow.set_tracking_uri(project_path("mlruns").as_uri())
    mlflow.set_experiment(reg_cfg["mlflow_experiment"])

    with mlflow.start_run(run_name="train") as parent_run:
        mlflow.log_params({f"base.{k}": v for k, v in base_params.items()})
        mlflow.log_param("cv_folds", train_cfg["cv_folds"])
        mlflow.log_param("optuna_trials", train_cfg["optuna_trials"])

        study = optuna.create_study(
            direction="maximize",
            sampler=optuna.samplers.TPESampler(seed=train_cfg["random_state"]),
            pruner=optuna.pruners.MedianPruner(n_warmup_steps=2),
        )
        study.optimize(
            lambda t: cv_objective(
                t,
                X,
                y,
                base_params,
                cv_folds=train_cfg["cv_folds"],
                early_stopping_rounds=train_cfg["early_stopping_rounds"],
                random_state=train_cfg["random_state"],
            ),
            n_trials=train_cfg["optuna_trials"],
            show_progress_bar=False,
        )

        best = study.best_params
        mlflow.log_params({f"best.{k}": v for k, v in best.items()})
        mlflow.log_metric("best_cv_auc", float(study.best_value))

        study_df = study.trials_dataframe()
        study_csv = reports_dir / "optuna_study.csv"
        study_df.to_csv(study_csv, index=False)
        mlflow.log_artifact(str(study_csv))

        final_params = {**base_params, **best}
        final_model = lgb.LGBMClassifier(**final_params)
        final_model.fit(X, y)

        model_path = models_dir / "model.joblib"
        joblib.dump({"model": final_model, "feature_names": list(X.columns)}, model_path)
        mlflow.log_artifact(str(model_path), artifact_path="model")
        mlflow.set_tag("phase", "train")
        log.info("train.done", best_auc=float(study.best_value), run_id=parent_run.info.run_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
