"""Contract tests for the serving API."""

from __future__ import annotations

import pytest


@pytest.mark.integration
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert isinstance(body["feature_count"], int)
    assert body["feature_count"] > 0


@pytest.mark.integration
def test_metrics(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    # Prometheus exposition contains our counter definitions
    assert "api_requests_total" in r.text
    assert "model_predictions_total" in r.text


@pytest.mark.integration
def test_predict_single(client, sample_application):
    r = client.post("/predict", json={"applications": [sample_application]})
    assert r.status_code == 200
    body = r.json()
    assert body["model_version"]
    assert len(body["predictions"]) == 1
    pred = body["predictions"][0]
    assert 0.0 <= pred["probability_of_default"] <= 1.0
    assert pred["decision"] in {"approve", "review", "deny"}
    assert r.headers["x-request-id"]


@pytest.mark.integration
def test_predict_batch(client, sample_application):
    apps = [sample_application] * 3
    r = client.post("/predict", json={"applications": apps})
    assert r.status_code == 200
    body = r.json()
    assert len(body["predictions"]) == 3


@pytest.mark.integration
def test_predict_rejects_invalid_sex(client, sample_application):
    bad = {**sample_application, "sex": 9}
    r = client.post("/predict", json={"applications": [bad]})
    assert r.status_code == 422


@pytest.mark.integration
def test_predict_rejects_empty_batch(client):
    r = client.post("/predict", json={"applications": []})
    assert r.status_code == 422


@pytest.mark.integration
def test_explain_returns_top_drivers(client, sample_application):
    r = client.post("/explain", json={"application": sample_application})
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["probability_of_default"] <= 1.0
    assert body["decision"] in {"approve", "review", "deny"}
    assert len(body["top_drivers"]) > 0
    for d in body["top_drivers"]:
        assert "feature" in d
        assert isinstance(d["shap_value"], float)
