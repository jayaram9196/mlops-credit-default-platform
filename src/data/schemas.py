"""Pandera schema for the UCI 'Default of Credit Card Clients' (Taiwan) dataset.

Non-strict — upstream additions don't break validation; the columns listed below
are the ones the pipeline depends on.
"""

from __future__ import annotations

import pandera.pandas as pa

PAY_COLS = ["PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6"]
BILL_COLS = [f"BILL_AMT{i}" for i in range(1, 7)]
PAY_AMT_COLS = [f"PAY_AMT{i}" for i in range(1, 7)]


application_schema = pa.DataFrameSchema(
    columns={
        "LIMIT_BAL": pa.Column(float, checks=pa.Check.gt(0)),
        "SEX": pa.Column(int, checks=pa.Check.isin([1, 2])),
        "EDUCATION": pa.Column(int, checks=pa.Check.in_range(1, 4)),
        "MARRIAGE": pa.Column(int, checks=pa.Check.in_range(1, 3)),
        "AGE": pa.Column(int, checks=pa.Check.in_range(18, 100)),
        **{c: pa.Column(int, checks=pa.Check.in_range(-2, 9)) for c in PAY_COLS},
        **{c: pa.Column(float) for c in BILL_COLS},
        **{c: pa.Column(float, checks=pa.Check.ge(0)) for c in PAY_AMT_COLS},
        "TARGET": pa.Column(int, checks=pa.Check.isin([0, 1])),
    },
    strict=False,
    coerce=True,
)
