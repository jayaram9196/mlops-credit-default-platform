"""Ingestion stage: fetch UCI 'Default of Credit Card Clients' (id=350).

The dataset is fetched via the `ucimlrepo` package (cached in `~/.ucimlrepo`), the
ID column is dropped, the target column is renamed to `TARGET`, and a stratified
train/holdout split is written to `data/interim/`.

Idempotent: rerunning skips the network fetch if `data/raw/credit_default.csv`
is already present.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from src.utils import configure_logging, ensure_dir, get_logger, load_params, project_path

log = get_logger(__name__)

RAW_FILENAME = "credit_default.csv"
TARGET_COLUMN = "TARGET"


OPENML_DATA_ID = 42477  # OpenML mirror of UCI dataset 350

# OpenML strips the original UCI headers to x1..x23. The row order, value
# coding, and target match the UCI distribution exactly — we just rename.
OPENML_COLUMN_MAP = {
    "x1": "LIMIT_BAL",
    "x2": "SEX",
    "x3": "EDUCATION",
    "x4": "MARRIAGE",
    "x5": "AGE",
    "x6": "PAY_0",
    "x7": "PAY_2",
    "x8": "PAY_3",
    "x9": "PAY_4",
    "x10": "PAY_5",
    "x11": "PAY_6",
    "x12": "BILL_AMT1",
    "x13": "BILL_AMT2",
    "x14": "BILL_AMT3",
    "x15": "BILL_AMT4",
    "x16": "BILL_AMT5",
    "x17": "BILL_AMT6",
    "x18": "PAY_AMT1",
    "x19": "PAY_AMT2",
    "x20": "PAY_AMT3",
    "x21": "PAY_AMT4",
    "x22": "PAY_AMT5",
    "x23": "PAY_AMT6",
    "y": TARGET_COLUMN,
}
INT_COLUMNS = ["SEX", "EDUCATION", "MARRIAGE", "AGE",
               "PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6"]


def fetch_uci(dataset_id: int) -> pd.DataFrame:
    """Fetch the UCI 'Default of Credit Card Clients' dataset via OpenML.

    We use OpenML's mirror (data_id=42477) instead of `ucimlrepo` because the
    archive.ics.uci.edu TLS certificate is currently expired, causing direct
    fetches to fail with SSLCertVerificationError. OpenML serves the same rows
    with generic `x1..x23` column names that we rename to the canonical UCI
    schema documented in `docs/problem-statement.md`.

    The `dataset_id` argument is preserved in the signature for forward
    compatibility with a future ucimlrepo-based code path.
    """
    from sklearn.datasets import fetch_openml

    log.info("data.ingest.openml.fetch.start", data_id=OPENML_DATA_ID, uci_id=dataset_id)
    bundle = fetch_openml(data_id=OPENML_DATA_ID, as_frame=True, parser="pandas")
    df = bundle.frame.rename(columns=OPENML_COLUMN_MAP).copy()
    df[TARGET_COLUMN] = df[TARGET_COLUMN].astype(int)
    for c in INT_COLUMNS:
        if c in df.columns:
            df[c] = df[c].astype(int)
    log.info("data.ingest.openml.fetch.done", rows=len(df), cols=df.shape[1])
    return df


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop(columns=[c for c in ("ID",) if c in df.columns])
    # EDUCATION raw values include 0, 5, 6 which the dataset card flags as "other".
    if "EDUCATION" in df.columns:
        df["EDUCATION"] = df["EDUCATION"].where(df["EDUCATION"].isin([1, 2, 3, 4]), 4)
    if "MARRIAGE" in df.columns:
        df["MARRIAGE"] = df["MARRIAGE"].where(df["MARRIAGE"].isin([1, 2, 3]), 3)
    return df


def stratified_split(
    df: pd.DataFrame, target: str, test_size: float, random_state: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    train, holdout = train_test_split(
        df, test_size=test_size, random_state=random_state, stratify=df[target]
    )
    return train.reset_index(drop=True), holdout.reset_index(drop=True)


def main() -> int:
    configure_logging()
    params = load_params()
    cfg = params["data_ingestion"]

    raw_dir = ensure_dir(project_path(cfg["raw_dir"]))
    interim_dir = ensure_dir(project_path("data/interim"))
    raw_path = raw_dir / RAW_FILENAME

    if raw_path.exists():
        log.info("data.ingest.skip", reason="raw exists", path=str(raw_path))
        df = pd.read_csv(raw_path)
    else:
        df = fetch_uci(cfg["uci_dataset_id"])
        df = normalize(df)
        df.to_csv(raw_path, index=False)
        log.info("data.ingest.saved", path=str(raw_path), rows=len(df))

    train, holdout = stratified_split(
        df,
        target=TARGET_COLUMN,
        test_size=cfg["test_size"],
        random_state=cfg["random_state"],
    )

    train_path = interim_dir / "credit_default_train.csv"
    holdout_path = interim_dir / "credit_default_holdout.csv"
    train.to_csv(train_path, index=False)
    holdout.to_csv(holdout_path, index=False)

    log.info(
        "data.ingest.split.done",
        train_rows=len(train),
        holdout_rows=len(holdout),
        train_default_rate=float(train[TARGET_COLUMN].mean()),
        holdout_default_rate=float(holdout[TARGET_COLUMN].mean()),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
