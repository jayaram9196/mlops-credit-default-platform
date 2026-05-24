"""Validation stage: assert the pandera schema on the split data.

Writes `reports/validation.json` with row counts and violation counts. Exits
non-zero when `fail_on_violation: true` and any violations exist.
"""

from __future__ import annotations

import json
import sys

import pandas as pd
import pandera.pandas as pa

from src.data.schemas import application_schema
from src.utils import configure_logging, ensure_dir, get_logger, load_params, project_path

log = get_logger(__name__)


def validate_frame(df: pd.DataFrame, schema: pa.DataFrameSchema, name: str) -> dict:
    try:
        schema.validate(df, lazy=True)
        return {"dataset": name, "rows": len(df), "violations": 0}
    except pa.errors.SchemaErrors as exc:
        log.warning("data.validate.fail", dataset=name, failure_cases=len(exc.failure_cases))
        return {
            "dataset": name,
            "rows": len(df),
            "violations": int(len(exc.failure_cases)),
            "examples": exc.failure_cases.head(5).to_dict(orient="records"),
        }


def main() -> int:
    configure_logging()
    params = load_params()
    cfg = params["data_validation"]

    interim = project_path("data/interim")
    reports_dir = ensure_dir(project_path("reports"))

    train = pd.read_csv(interim / "credit_default_train.csv")
    holdout = pd.read_csv(interim / "credit_default_holdout.csv")

    results = [
        validate_frame(train, application_schema, "credit_default_train"),
        validate_frame(holdout, application_schema, "credit_default_holdout"),
    ]

    total_violations = sum(r["violations"] for r in results)
    report = {"total_violations": total_violations, "datasets": results}

    out = reports_dir / "validation.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    log.info("data.validate.done", total_violations=total_violations, report=str(out))

    if cfg["fail_on_violation"] and total_violations > 0:
        log.error("data.validate.fail.gate", total_violations=total_violations)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
