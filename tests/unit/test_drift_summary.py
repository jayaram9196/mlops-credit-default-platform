"""Unit tests for drift summary aggregation logic.

We don't import Evidently here — the wrapped `summarise` function works off the
snapshot's `.dict()` payload, which we can fixture directly.
"""

from __future__ import annotations

import pytest

from src.monitoring.drift import DriftSummary, summarise


class _FakeSnapshot:
    def __init__(self, payload: dict):
        self._payload = payload

    def dict(self) -> dict:
        return self._payload


@pytest.mark.unit
def test_summarise_counts_drifted_columns():
    snapshot = _FakeSnapshot(
        {
            "metrics": [
                {
                    "result": {
                        "drift_by_columns": {
                            "LIMIT_BAL": {"drift_detected": True, "drift_score": 0.12},
                            "AGE": {"drift_detected": False, "drift_score": 0.02},
                            "PAY_0": {"drift_detected": True, "drift_score": 0.30},
                        }
                    }
                }
            ]
        }
    )
    s = summarise(snapshot)
    assert isinstance(s, DriftSummary)
    assert s.n_columns == 3
    assert s.n_drifted == 2
    assert s.share_drifted == pytest.approx(2 / 3)
    assert s.drift_per_column["PAY_0"] == 0.30


@pytest.mark.unit
def test_summarise_handles_empty_payload():
    snapshot = _FakeSnapshot({"metrics": []})
    s = summarise(snapshot)
    assert s.n_columns == 0
    assert s.n_drifted == 0
    assert s.share_drifted == 0.0
