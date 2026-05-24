"""Gating logic should reject models that miss any threshold."""

from __future__ import annotations

import pytest

from src.models.register import passes_gates


EVAL_CFG = {
    "min_auc_for_promotion": 0.76,
    "max_demographic_parity_diff": 0.05,
    "max_equal_opportunity_diff": 0.05,
}


@pytest.mark.unit
def test_passes_when_all_metrics_meet_thresholds():
    metrics = {
        "auc": 0.78,
        "fairness": [
            {"attribute": "CODE_GENDER", "demographic_parity_diff": 0.02,
             "equal_opportunity_diff": 0.03},
        ],
    }
    ok, reasons = passes_gates(metrics, EVAL_CFG)
    assert ok
    assert reasons == []


@pytest.mark.unit
def test_fails_on_low_auc():
    metrics = {"auc": 0.70, "fairness": []}
    ok, reasons = passes_gates(metrics, EVAL_CFG)
    assert not ok
    assert any("AUC" in r for r in reasons)


@pytest.mark.unit
def test_fails_on_fairness_violation():
    metrics = {
        "auc": 0.80,
        "fairness": [
            {"attribute": "CODE_GENDER", "demographic_parity_diff": 0.20,
             "equal_opportunity_diff": 0.01},
        ],
    }
    ok, reasons = passes_gates(metrics, EVAL_CFG)
    assert not ok
    assert any("demographic_parity_diff" in r for r in reasons)
