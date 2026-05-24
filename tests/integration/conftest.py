"""Pytest fixtures for serving integration tests.

Requires the Phase 1 pipeline to have already run (model.joblib +
transformer.joblib present in `models/`).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    from src.serving.app import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_application() -> dict:
    return {
        "limit_bal": 50000,
        "sex": 1,
        "education": 2,
        "marriage": 1,
        "age": 35,
        "pay_0": 0,
        "pay_2": 0,
        "pay_3": 0,
        "pay_4": 0,
        "pay_5": 0,
        "pay_6": 0,
        "bill_amt1": 1500,
        "bill_amt2": 1400,
        "bill_amt3": 1300,
        "bill_amt4": 1200,
        "bill_amt5": 1100,
        "bill_amt6": 1000,
        "pay_amt1": 500,
        "pay_amt2": 500,
        "pay_amt3": 500,
        "pay_amt4": 500,
        "pay_amt5": 500,
        "pay_amt6": 500,
    }
