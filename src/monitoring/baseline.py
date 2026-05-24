"""Capture a baseline snapshot from the training split for drift detection.

`evidently` compares a `current` window against a `reference`. The reference is
captured once after each successful train/promote cycle and pinned by the model
version that produced it. This module produces that reference.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from src.utils import configure_logging, ensure_dir, get_logger, project_path

log = get_logger(__name__)

DEFAULT_TRAIN_PARQUET = project_path("data/processed/train.parquet")
DEFAULT_BASELINE_DIR = project_path("monitoring/state")


def capture_baseline(train_path: Path, out_dir: Path, sample_size: int = 10_000) -> Path:
    df = pd.read_parquet(train_path)
    sample = df.sample(min(sample_size, len(df)), random_state=42).reset_index(drop=True)
    ensure_dir(out_dir)
    out = out_dir / "reference.parquet"
    sample.to_parquet(out, index=False)
    log.info(
        "monitoring.baseline.saved",
        rows=len(sample),
        cols=sample.shape[1],
        path=str(out),
    )
    return out


def main() -> int:
    configure_logging()
    capture_baseline(DEFAULT_TRAIN_PARQUET, DEFAULT_BASELINE_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
