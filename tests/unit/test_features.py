"""Unit tests for feature-engineering helpers (UCI Taiwan dataset)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features.build import (
    add_age_bin,
    bill_features,
    drop_high_missing,
    pay_status_features,
    payment_features,
    split_dtypes,
    utilisation_features,
)


def _row(**kw) -> dict:
    base = {
        "LIMIT_BAL": 50000.0,
        "SEX": 1,
        "EDUCATION": 2,
        "MARRIAGE": 1,
        "AGE": 35,
        "PAY_0": 0, "PAY_2": 0, "PAY_3": 0, "PAY_4": 0, "PAY_5": 0, "PAY_6": 0,
        "BILL_AMT1": 1000.0, "BILL_AMT2": 1100.0, "BILL_AMT3": 1200.0,
        "BILL_AMT4": 1300.0, "BILL_AMT5": 1400.0, "BILL_AMT6": 1500.0,
        "PAY_AMT1": 500.0, "PAY_AMT2": 500.0, "PAY_AMT3": 500.0,
        "PAY_AMT4": 500.0, "PAY_AMT5": 500.0, "PAY_AMT6": 500.0,
        "TARGET": 0,
    }
    base.update(kw)
    return base


@pytest.mark.unit
def test_pay_status_counts_delays_and_max():
    df = pd.DataFrame(
        [
            _row(PAY_0=2, PAY_2=1),
            _row(),
        ]
    )
    out = pay_status_features(df)
    assert out.loc[0, "PAY_DELAY_COUNT"] == 2
    assert out.loc[0, "PAY_DELAY_MAX"] == 2
    assert out.loc[0, "PAY_DELAY_LAST"] == 2
    assert out.loc[1, "PAY_DELAY_COUNT"] == 0


@pytest.mark.unit
def test_bill_trend_is_positive_when_bill_grows():
    df = pd.DataFrame([_row()])  # bills monotonically increasing
    out = bill_features(df)
    assert out.loc[0, "BILL_TREND"] > 0


@pytest.mark.unit
def test_payment_features_counts_zeros():
    df = pd.DataFrame([_row(PAY_AMT1=0, PAY_AMT2=0)])
    out = payment_features(df)
    assert out.loc[0, "PAYAMT_ZERO_COUNT"] == 2


@pytest.mark.unit
def test_utilisation_handles_zero_limit():
    df = pd.DataFrame([_row(LIMIT_BAL=0)])
    out = utilisation_features(df)
    assert np.isnan(out.loc[0, "UTILISATION_LAST"])


@pytest.mark.unit
def test_age_bin_buckets_correctly():
    df = pd.DataFrame({"AGE": [22, 30, 40]})
    out = add_age_bin(df)
    assert out.loc[0, "AGE_BIN"] == "18-25"
    assert out.loc[1, "AGE_BIN"] == "26-35"
    assert out.loc[2, "AGE_BIN"] == "36-45"


@pytest.mark.unit
def test_drop_high_missing_respects_protected_columns():
    df = pd.DataFrame(
        {
            "x_full": [1, 2, 3, 4],
            "x_sparse": [None, None, None, 1],
            "TARGET": [0, 1, 0, 1],
        }
    )
    out = drop_high_missing(df, threshold=0.5, protect=["TARGET"])
    assert "TARGET" in out.columns
    assert "x_full" in out.columns
    assert "x_sparse" not in out.columns


@pytest.mark.unit
def test_split_dtypes_separates_correctly():
    df = pd.DataFrame({"n": [1, 2], "c": ["a", "b"], "drop": [9, 9]})
    num, cat = split_dtypes(df, exclude=["drop"])
    assert num == ["n"]
    assert cat == ["c"]
