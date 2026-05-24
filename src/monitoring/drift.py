"""Data + prediction drift detection using Evidently.

Inputs:
- reference.parquet  → snapshot captured at training time
- current.parquet    → recent production features + predictions

Output:
- reports/drift/drift-<timestamp>.json   metrics
- reports/drift/drift-<timestamp>.html   human-readable report
- non-zero exit if any column's drift score exceeds the threshold

Designed to run on a schedule (Kubernetes CronJob, Airflow DAG, or Step
Functions task) and feed Alertmanager via the API's `/metrics` endpoint or via
the CronJob's exit code.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.utils import configure_logging, ensure_dir, get_logger, load_params, project_path

log = get_logger(__name__)


@dataclass
class DriftSummary:
    timestamp: str
    n_columns: int
    n_drifted: int
    share_drifted: float
    drift_per_column: dict[str, float]

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "n_columns": self.n_columns,
            "n_drifted": self.n_drifted,
            "share_drifted": self.share_drifted,
            "drift_per_column": self.drift_per_column,
        }


def _build_report(reference: pd.DataFrame, current: pd.DataFrame):
    # Lazy import — keeps the train/evaluate stages lightweight.
    from evidently import Report
    from evidently.presets import DataDriftPreset

    common = [c for c in reference.columns if c in current.columns]
    reference = reference[common]
    current = current[common]
    report = Report(metrics=[DataDriftPreset()])
    snapshot = report.run(reference_data=reference, current_data=current)
    return snapshot


def summarise(snapshot) -> DriftSummary:
    payload = snapshot.dict()
    metrics = payload.get("metrics", [])
    drift_per_column: dict[str, float] = {}
    n_drifted = 0
    n_columns = 0
    for m in metrics:
        result = m.get("result", {})
        for col, info in (result.get("drift_by_columns") or {}).items():
            n_columns += 1
            score = float(info.get("drift_score") or 0.0)
            drift_per_column[col] = score
            if info.get("drift_detected"):
                n_drifted += 1
    share = (n_drifted / n_columns) if n_columns else 0.0
    return DriftSummary(
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        n_columns=n_columns,
        n_drifted=n_drifted,
        share_drifted=share,
        drift_per_column=drift_per_column,
    )


def run_drift_check(
    reference_path: Path,
    current_path: Path,
    out_dir: Path,
    fail_share_threshold: float,
) -> int:
    reference = pd.read_parquet(reference_path)
    current = pd.read_parquet(current_path)

    snapshot = _build_report(reference, current)
    summary = summarise(snapshot)

    out_dir = ensure_dir(out_dir)
    ts = summary.timestamp.replace(":", "-")
    (out_dir / f"drift-{ts}.json").write_text(json.dumps(summary.to_dict(), indent=2))
    snapshot.save_html(str(out_dir / f"drift-{ts}.html"))

    log.info(
        "monitoring.drift.summary",
        n_columns=summary.n_columns,
        n_drifted=summary.n_drifted,
        share_drifted=round(summary.share_drifted, 3),
        fail_threshold=fail_share_threshold,
    )

    if summary.share_drifted > fail_share_threshold:
        log.error(
            "monitoring.drift.exceeded",
            share=summary.share_drifted,
            threshold=fail_share_threshold,
        )
        return 1
    return 0


def main() -> int:
    configure_logging()
    params = load_params()
    cfg = params.get("monitoring", {})
    ref = Path(cfg.get("reference_path", "monitoring/state/reference.parquet"))
    cur = Path(cfg.get("current_path", "monitoring/state/current.parquet"))
    out = Path(cfg.get("reports_dir", "reports/drift"))
    threshold = float(cfg.get("share_drifted_threshold", 0.30))
    return run_drift_check(project_path(ref), project_path(cur), project_path(out), threshold)


if __name__ == "__main__":
    sys.exit(main())
