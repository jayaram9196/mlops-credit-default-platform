"""Pandera schema sanity checks for the UCI Taiwan default dataset."""

from __future__ import annotations

import pandas as pd
import pandera.pandas as pa
import pytest

from src.data.schemas import application_schema


def _good_row(**overrides) -> dict:
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
    base.update(overrides)
    return base


@pytest.mark.unit
def test_schema_accepts_valid_rows():
    df = pd.DataFrame([_good_row(), _good_row()])
    application_schema.validate(df)


@pytest.mark.unit
def test_schema_rejects_unknown_sex():
    df = pd.DataFrame([_good_row(SEX=9)])
    with pytest.raises(pa.errors.SchemaError):
        application_schema.validate(df)


@pytest.mark.unit
def test_schema_rejects_non_positive_limit_bal():
    df = pd.DataFrame([_good_row(LIMIT_BAL=0.0)])
    with pytest.raises(pa.errors.SchemaError):
        application_schema.validate(df)


@pytest.mark.unit
def test_schema_rejects_age_too_young():
    df = pd.DataFrame([_good_row(AGE=10)])
    with pytest.raises(pa.errors.SchemaError):
        application_schema.validate(df)


@pytest.mark.unit
def test_schema_rejects_negative_pay_amt():
    df = pd.DataFrame([_good_row(PAY_AMT1=-1.0)])
    with pytest.raises(pa.errors.SchemaError):
        application_schema.validate(df)
