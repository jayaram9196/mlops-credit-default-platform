"""Prometheus metrics for the serving API."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter(
    "api_requests_total",
    "Total HTTP requests received.",
    labelnames=("endpoint", "method", "status"),
)

REQUEST_LATENCY = Histogram(
    "api_request_duration_seconds",
    "Request latency in seconds.",
    labelnames=("endpoint", "method"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

PREDICTION_COUNT = Counter(
    "model_predictions_total",
    "Number of predictions returned, labelled by decision.",
    labelnames=("decision",),
)

PREDICTION_SCORE = Histogram(
    "model_prediction_score",
    "Distribution of P(default) returned.",
    buckets=(0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)
