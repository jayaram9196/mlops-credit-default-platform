"""Unit tests for Kamiran-Calders sample reweighing."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models.reweighing import compute_weights, weight_summary


@pytest.mark.unit
def test_balanced_outcomes_get_unit_weights():
    # Equal base rate across groups -> reweighing is a no-op
    y = pd.Series([0, 1, 0, 1, 0, 1, 0, 1])
    s = pd.Series(["a", "a", "a", "a", "b", "b", "b", "b"])
    w = compute_weights(y, s)
    assert np.allclose(w, 1.0)


@pytest.mark.unit
def test_skewed_subgroup_gets_compensating_weights():
    # Group "a" has 25% default; group "b" has 75% default.
    # Reweighing should up-weight the under-represented (y, s) cells.
    y = pd.Series([0, 0, 0, 1, 0, 1, 1, 1])
    s = pd.Series(["a", "a", "a", "a", "b", "b", "b", "b"])
    w = compute_weights(y, s)
    # Defaults in group a are under-represented vs marginal -> weight > 1.
    a_default = w[(s == "a") & (y == 1)].mean()
    a_nondefault = w[(s == "a") & (y == 0)].mean()
    b_default = w[(s == "b") & (y == 1)].mean()
    b_nondefault = w[(s == "b") & (y == 0)].mean()
    assert a_default > 1.0
    assert a_nondefault < 1.0
    assert b_nondefault > 1.0
    assert b_default < 1.0


@pytest.mark.unit
def test_post_weighting_joint_factorises_to_marginals():
    # After weighting, weighted P(Y=1 | S=s) should equal weighted P(Y=1).
    rng = np.random.default_rng(42)
    n = 1000
    s = pd.Series(rng.choice(["a", "b", "c"], size=n))
    y = pd.Series(rng.integers(0, 2, size=n))
    # introduce skew: group "a" is more likely to be 1
    mask = (s == "a") & (rng.random(n) < 0.7)
    y[mask] = 1
    w = compute_weights(y, s)
    weighted_p_y = (w * y).sum() / w.sum()
    for s_val in s.unique():
        m = s == s_val
        cond = (w[m] * y[m]).sum() / w[m].sum()
        assert abs(cond - weighted_p_y) < 1e-9


@pytest.mark.unit
def test_composite_sensitive_produces_finer_cells():
    y = pd.Series([0, 1, 0, 1, 0, 1, 0, 1])
    s1 = pd.Series(["a", "a", "b", "b", "a", "a", "b", "b"])
    s2 = pd.Series(["x", "x", "x", "x", "y", "y", "y", "y"])
    summary = weight_summary(compute_weights(y, s1, s2), y, s1, s2)
    # 4 (a|x, a|y, b|x, b|y) groups × 2 outcomes = 8 cells max
    assert "|" in summary["sensitive"].iloc[0]
    assert len(summary) <= 8


@pytest.mark.unit
def test_length_mismatch_raises():
    y = pd.Series([0, 1])
    s = pd.Series(["a", "b", "c"])
    with pytest.raises(ValueError):
        compute_weights(y, s)


@pytest.mark.unit
def test_no_sensitive_attribute_raises():
    y = pd.Series([0, 1])
    with pytest.raises(ValueError):
        compute_weights(y)
