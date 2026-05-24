# Monitoring & Drift

Three layers, all driven off the same `/metrics` endpoint the FastAPI service
already exposes:

| Layer | Tool | Source of truth |
| --- | --- | --- |
| Service health (latency, errors, replicas) | Prometheus + Grafana | `api_requests_total`, `api_request_duration_seconds`, kube-state-metrics |
| Model behaviour (decision mix, score distribution) | Prometheus + Grafana | `model_predictions_total`, `model_prediction_score` histogram |
| Data + concept drift | Evidently AI + scheduled CronJob | parquet snapshots in S3, scored via [`src/monitoring/drift.py`](../src/monitoring/drift.py) |

## Layout

```
monitoring/
  prometheus/rules.yaml         recording + alerting rules
  alertmanager/config.example.yaml  Slack routing scaffold
  grafana/dashboards/
    credit-default-sre.json     request rate, error rate, latency, HPA, restarts
    credit-default-ml.json      decision mix, score histogram, drift gauge
  state/                        runtime artefacts (reference.parquet etc.)
```

Drift code lives in [`src/monitoring/`](../src/monitoring/) so the same
container image powers the API *and* the scheduled drift job.

## Wiring on a cluster

Assuming kube-prometheus-stack is installed in `monitoring`:

```bash
# 1) enable the ServiceMonitor in the chart so Prometheus scrapes /metrics
helm upgrade --install credit-default-api k8s/helm/credit-default-api \
  -n credit-default --create-namespace \
  --set serviceMonitor.enabled=true \
  --set serviceMonitor.labels.release=prometheus

# 2) load PrometheusRule
kubectl apply -n monitoring -f monitoring/prometheus/rules.yaml

# 3) import dashboards (Grafana UI -> Import -> upload JSON)
#    or wire as a configmap with grafana.dashboards label = 1
```

## Drift CronJob

Enabled via the Helm chart:

```bash
helm upgrade --install credit-default-api k8s/helm/credit-default-api \
  -n credit-default \
  --set drift.enabled=true \
  --set drift.referenceUri=s3://<artifacts-bucket>/monitoring/reference.parquet \
  --set drift.currentUri=s3://<data-bucket>/monitoring/current.parquet \
  --set drift.schedule="0 */6 * * *"
```

Producing the reference snapshot once after each successful train:

```bash
python -m src.monitoring.baseline
```

The CronJob's container runs `python -m src.monitoring.drift`, which exits
non-zero when the share of drifted columns exceeds
`monitoring.share_drifted_threshold` in [params.yaml](../params.yaml). A
failure surfaces as a `Job` failure → Alertmanager via kube-state-metrics.

## Local smoke

```bash
# Once you have data/processed/train.parquet (Phase 1 done):
python -m src.monitoring.baseline       # writes monitoring/state/reference.parquet
cp monitoring/state/reference.parquet monitoring/state/current.parquet  # no drift
python -m src.monitoring.drift          # exit 0, writes reports/drift/*.json
```
