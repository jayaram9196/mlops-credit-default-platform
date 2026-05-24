# Airflow — credit-default retrain DAG

A single weekly DAG that re-runs the Phase 1 pipeline and, if it passes the
fairness + AUC gates in `src/models/register.py`, sets the new image tag on the
Argo Rollout in `credit-default` namespace. Argo Rollouts then drives the
canary.

```
drift_check ─┬─▶ ingest ─▶ validate ─▶ features ─▶ train ─▶ evaluate ─▶ register ─▶ trigger_canary ─▶ build_message ─▶ notify_slack
             │
             └─ (no drift, no force) ─▶ skip downstream via ShortCircuit
```

## Wiring

| Resource | How it's set |
| --- | --- |
| `SLACK_CONN_ID` | Airflow Connection named `slack_default` (webhook URL) |
| `var.value.api_image_repository` | Airflow Variable, e.g. `ghcr.io/jayaram9196/mlops-credit-default-platform` |
| `var.value.api_image_tag_staging` | Airflow Variable, written by the GitHub Actions `build-deploy` workflow after a successful build to point at the new git-sha tag |
| `PROJECT_DIR` env var | Path inside the worker container where the repo is mounted |

## Deploying

Pick one:

1. **MWAA / Composer / Cloud Composer**: drop `airflow/dags/credit_default_retrain.py` into the bucket; add the Slack connection + variables via the UI.
2. **Self-hosted via the official Helm chart**: include `airflow/dags/` as a Git-Sync source and add `airflow/requirements.txt` to the worker image.
3. **Local smoke**:
   ```bash
   pip install apache-airflow==2.9.* apache-airflow-providers-slack
   AIRFLOW_HOME=$PWD/airflow_home airflow standalone
   # then airflow dags list, airflow dags trigger credit_default_retrain
   ```

## Force a run (no drift required)

```bash
airflow dags trigger credit_default_retrain --conf '{"force": true}'
```

## Alternate path — AWS Step Functions

For shops without Airflow, the same pipeline runs as an AWS Step Functions
state machine — see [pipelines/step-functions/retrain.asl.json](../pipelines/step-functions/retrain.asl.json).
The state machine launches a SageMaker training job, invokes a Lambda for
fairness gating, and updates the image tag on EKS via a Lambda → kubectl shim
(the Argo Rollout watches for it).
