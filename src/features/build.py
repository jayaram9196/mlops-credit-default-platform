"""Feature engineering for the UCI Taiwan credit-default dataset.

Steps:
1. Load the split train + holdout frames.
2. Derive aggregations across the 6-month PAY_X / BILL_AMTX / PAY_AMTX windows.
3. Derive credit-utilisation ratios and an AGE_BIN for fairness analysis.
4. Drop columns above the missing-value threshold (protected columns are kept).
5. Fit a sklearn ColumnTransformer on the training split only; transform both.
6. Persist processed parquets and the fitted transformer.
"""

from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.utils import configure_logging, ensure_dir, get_logger, load_params, project_path

log = get_logger(__name__)

TARGET = "TARGET"
PAY_COLS = ["PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6"]
BILL_COLS = [f"BILL_AMT{i}" for i in range(1, 7)]
PAY_AMT_COLS = [f"PAY_AMT{i}" for i in range(1, 7)]
PROTECTED_RAW = ["SEX", "EDUCATION", "MARRIAGE", "AGE_BIN"]
CATEGORICAL_INT_COLS = ["SEX", "EDUCATION", "MARRIAGE"]


def pay_status_features(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in PAY_COLS if c in df.columns]
    pay = df[cols]
    out = pd.DataFrame(index=df.index)
    out["PAY_DELAY_COUNT"] = (pay > 0).sum(axis=1)
    out["PAY_DELAY_MAX"] = pay.max(axis=1)
    out["PAY_DELAY_MEAN"] = pay.mean(axis=1)
    out["PAY_DELAY_LAST"] = pay[cols[0]]
    return out


def bill_features(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in BILL_COLS if c in df.columns]
    bill = df[cols]
    out = pd.DataFrame(index=df.index)
    out["BILL_MEAN"] = bill.mean(axis=1)
    out["BILL_MAX"] = bill.max(axis=1)
    out["BILL_STD"] = bill.std(axis=1)
    x = np.arange(len(cols))
    x_centered = x - x.mean()
    denom = float((x_centered**2).sum()) or 1.0
    bx = bill.to_numpy()
    out["BILL_TREND"] = (bx * x_centered).sum(axis=1) / denom
    return out


def payment_features(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in PAY_AMT_COLS if c in df.columns]
    pay = df[cols]
    out = pd.DataFrame(index=df.index)
    out["PAYAMT_MEAN"] = pay.mean(axis=1)
    out["PAYAMT_MAX"] = pay.max(axis=1)
    out["PAYAMT_ZERO_COUNT"] = (pay <= 0).sum(axis=1)
    return out


def utilisation_features(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    if {"LIMIT_BAL", "BILL_AMT1"}.issubset(df.columns):
        out["UTILISATION_LAST"] = df["BILL_AMT1"] / df["LIMIT_BAL"].replace(0, np.nan)
    if "LIMIT_BAL" in df.columns and all(c in df.columns for c in BILL_COLS):
        avg_bill = df[BILL_COLS].mean(axis=1)
        out["UTILISATION_MEAN"] = avg_bill / df["LIMIT_BAL"].replace(0, np.nan)
    if all(c in df.columns for c in BILL_COLS + PAY_AMT_COLS):
        total_bill = df[BILL_COLS].sum(axis=1).replace(0, np.nan)
        total_pay = df[PAY_AMT_COLS].sum(axis=1)
        out["PAY_TO_BILL_RATIO"] = total_pay / total_bill
    return out


def add_age_bin(df: pd.DataFrame) -> pd.DataFrame:
    if "AGE" not in df.columns:
        return df
    df = df.copy()
    df["AGE_BIN"] = pd.cut(
        df["AGE"],
        bins=[0, 25, 35, 45, 55, 65, 100],
        labels=["18-25", "26-35", "36-45", "46-55", "56-65", "66+"],
        include_lowest=True,
    ).astype("string")
    return df


def assemble(df: pd.DataFrame) -> pd.DataFrame:
    df = add_age_bin(df)
    return pd.concat(
        [
            df,
            pay_status_features(df),
            bill_features(df),
            payment_features(df),
            utilisation_features(df),
        ],
        axis=1,
    )


def drop_high_missing(df: pd.DataFrame, threshold: float, protect: list[str]) -> pd.DataFrame:
    missing = df.isna().mean()
    to_drop = [c for c, m in missing.items() if m > threshold and c not in protect]
    if to_drop:
        log.info("features.drop_high_missing", count=len(to_drop), threshold=threshold)
    return df.drop(columns=to_drop)


def split_dtypes(df: pd.DataFrame, exclude: list[str]) -> tuple[list[str], list[str]]:
    numeric = df.select_dtypes(include=["number"]).columns.tolist()
    categorical = df.select_dtypes(include=["object", "category", "string"]).columns.tolist()
    numeric = [c for c in numeric if c not in exclude]
    categorical = [c for c in categorical if c not in exclude]
    return numeric, categorical


def build_transformer(numeric: list[str], categorical: list[str]) -> ColumnTransformer:
    numeric_pipe = Pipeline(
        steps=[
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]
    )
    categorical_pipe = Pipeline(
        steps=[
            ("impute", SimpleImputer(strategy="most_frequent")),
            (
                "ohe",
                OneHotEncoder(handle_unknown="ignore", min_frequency=0.01, sparse_output=False),
            ),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipe, numeric),
            ("cat", categorical_pipe, categorical),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def coerce_categorical_ints(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in CATEGORICAL_INT_COLS:
        if c in df.columns:
            df[c] = df[c].astype("string")
    return df


def transform_and_save(
    transformer: ColumnTransformer,
    df: pd.DataFrame,
    feature_cols: list[str],
    out_path: Path,
    fit: bool,
    protected_cols: list[str],
) -> list[str]:
    X = df[feature_cols]
    arr = transformer.fit_transform(X) if fit else transformer.transform(X)
    names = transformer.get_feature_names_out().tolist()
    processed = pd.DataFrame(arr, columns=names, index=df.index)
    processed[TARGET] = df[TARGET].to_numpy()
    for c in protected_cols:
        if c in df.columns:
            processed[c] = df[c].to_numpy()
    processed.to_parquet(out_path, index=False)
    log.info("features.saved", path=str(out_path), rows=len(processed), cols=processed.shape[1])
    return names


def main() -> int:
    configure_logging()
    params = load_params()
    cfg = params["feature_engineering"]

    interim = project_path("data/interim")
    processed = ensure_dir(project_path("data/processed"))
    models_dir = ensure_dir(project_path("models"))

    train = pd.read_csv(interim / "credit_default_train.csv")
    holdout = pd.read_csv(interim / "credit_default_holdout.csv")

    train_full = coerce_categorical_ints(assemble(train))
    holdout_full = coerce_categorical_ints(assemble(holdout))

    protected = [c for c in PROTECTED_RAW if c in train_full.columns]
    keep_always = [TARGET, *protected]
    train_full = drop_high_missing(train_full, cfg["drop_threshold_missing"], protect=keep_always)
    holdout_full = holdout_full[train_full.columns.intersection(holdout_full.columns)]

    feature_cols = [c for c in train_full.columns if c not in {TARGET, *protected}]
    numeric, categorical = split_dtypes(train_full[feature_cols], exclude=[])

    transformer = build_transformer(numeric, categorical)
    feature_names = transform_and_save(
        transformer,
        train_full,
        feature_cols=feature_cols,
        out_path=processed / "train.parquet",
        fit=True,
        protected_cols=protected,
    )
    transform_and_save(
        transformer,
        holdout_full,
        feature_cols=feature_cols,
        out_path=processed / "holdout.parquet",
        fit=False,
        protected_cols=protected,
    )

    artifacts = {
        "transformer": transformer,
        "feature_names": feature_names,
        "numeric_columns": numeric,
        "categorical_columns": categorical,
    }
    joblib.dump(artifacts, models_dir / "transformer.joblib")
    log.info(
        "features.transformer.saved",
        path=str(models_dir / "transformer.joblib"),
        n_features=len(feature_names),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
