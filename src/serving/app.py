"""FastAPI application — `/predict`, `/explain`, `/health`, `/metrics`.

The model is loaded once at startup from the joblib artifacts produced by the
Phase 1 pipeline. The same artifacts that the DVC pipeline produces are used
here; in later phases this loader will be swapped for an MLflow-registry-backed
loader so the API picks up newly-promoted models without an image rebuild.
"""

from __future__ import annotations

import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from src.serving.inference import DecisionThresholds, ModelService
from src.serving.metrics import (
    PREDICTION_COUNT,
    PREDICTION_SCORE,
    REQUEST_COUNT,
    REQUEST_LATENCY,
)
from src.serving.schemas import (
    ExplanationRequest,
    ExplanationResponse,
    HealthResponse,
    PredictionRequest,
    PredictionResponse,
    PredictionResult,
)
from src.utils import configure_logging, get_logger, load_params, project_path

log = get_logger("serving")


def _load_service() -> ModelService:
    params = load_params()
    cfg = params["serving"]
    th = DecisionThresholds(
        deny=float(cfg["decision_thresholds"]["deny"]),
        review=float(cfg["decision_thresholds"]["review"]),
    )
    model_path = project_path(cfg["model_path"])
    transformer_path = project_path(cfg["transformer_path"])
    version = os.environ.get("MODEL_VERSION", "local-dev")
    log.info(
        "serving.load",
        model_path=str(model_path),
        transformer_path=str(transformer_path),
        version=version,
    )
    return ModelService.load(model_path, transformer_path, th, version=version)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    app.state.service = _load_service()
    log.info("serving.ready", features=len(app.state.service.feature_names))
    yield
    log.info("serving.shutdown")


app = FastAPI(
    title="Credit Default Risk API",
    version="0.1.0",
    description=(
        "Real-time scoring for loan applications. Returns probability of default "
        "plus an approve/review/deny decision, and per-prediction SHAP drivers."
    ),
    lifespan=lifespan,
)


@app.middleware("http")
async def telemetry(request: Request, call_next):
    started = time.perf_counter()
    request.state.request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    response = await call_next(request)
    elapsed = time.perf_counter() - started
    endpoint = request.url.path
    method = request.method
    REQUEST_COUNT.labels(endpoint=endpoint, method=method, status=response.status_code).inc()
    REQUEST_LATENCY.labels(endpoint=endpoint, method=method).observe(elapsed)
    response.headers["x-request-id"] = request.state.request_id
    log.info(
        "http.request",
        endpoint=endpoint,
        method=method,
        status=response.status_code,
        duration_ms=round(elapsed * 1000, 2),
        request_id=request.state.request_id,
    )
    return response


@app.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    svc: ModelService = request.app.state.service
    return HealthResponse(
        status="ok", model_version=svc.version, feature_count=len(svc.feature_names)
    )


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/predict", response_model=PredictionResponse)
def predict(payload: PredictionRequest, request: Request) -> PredictionResponse:
    svc: ModelService = request.app.state.service
    try:
        scored = svc.predict(payload.applications)
    except Exception as exc:
        log.error("predict.error", error=str(exc), request_id=request.state.request_id)
        raise HTTPException(status_code=500, detail="prediction failed") from exc

    predictions = [
        PredictionResult(probability_of_default=prob, decision=decision)
        for prob, decision in scored
    ]
    for p in predictions:
        PREDICTION_COUNT.labels(decision=p.decision).inc()
        PREDICTION_SCORE.observe(p.probability_of_default)

    return PredictionResponse(
        request_id=request.state.request_id,
        model_version=svc.version,
        predictions=predictions,
    )


@app.post("/explain", response_model=ExplanationResponse)
def explain(payload: ExplanationRequest, request: Request) -> ExplanationResponse:
    svc: ModelService = request.app.state.service
    params = load_params()
    top_k = int(params["serving"].get("shap_top_k", 5))
    try:
        prob, drivers = svc.explain(payload.application, top_k=top_k)
    except Exception as exc:
        log.error("explain.error", error=str(exc), request_id=request.state.request_id)
        raise HTTPException(status_code=500, detail="explanation failed") from exc

    decision = svc.thresholds.classify(prob)
    PREDICTION_COUNT.labels(decision=decision).inc()
    PREDICTION_SCORE.observe(prob)
    return ExplanationResponse(
        request_id=request.state.request_id,
        model_version=svc.version,
        probability_of_default=prob,
        decision=decision,
        top_drivers=drivers,
    )
