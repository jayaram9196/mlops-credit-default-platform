"""Weekly + drift-triggered retraining DAG for the credit-default model.

Graph:
    drift_check -> [ingest -> validate -> features -> train -> evaluate]
                                                                      \
                                                                       -> register -> trigger_canary -> notify_slack
                                                                      /
                                                                short_circuit_if_no_drift

The DAG runs on a weekly schedule but the drift check provides an out: if no
drift is detected and the schedule isn't a forced run, downstream stages are
skipped via a ShortCircuitOperator. The Phase 1 stages are invoked as
subprocess calls so the Airflow worker doesn't need the full ML stack baked in
(it does, in this image, but the contract is loose).

Image used by the KubernetesPodOperator-style tasks should match the prod API
image; that way features + training run against the exact code that's serving.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator, ShortCircuitOperator
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator

PROJECT_DIR = Path(os.environ.get("PROJECT_DIR", "/opt/airflow/credit-default-platform"))
DRIFT_THRESHOLD = float(os.environ.get("DRIFT_SHARE_THRESHOLD", "0.30"))
SLACK_CONN_ID = os.environ.get("SLACK_CONN_ID", "slack_default")

default_args = {
    "owner": "mlops",
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(hours=2),
    "email_on_failure": False,
}


def _import_drift():
    """Lazy import — the import path requires the project on PYTHONPATH."""
    import sys

    sys.path.insert(0, str(PROJECT_DIR))
    from src.monitoring.drift import run_drift_check  # noqa: WPS433 (runtime import)

    return run_drift_check


def check_drift(**context) -> bool:
    run_drift_check = _import_drift()
    ref = PROJECT_DIR / "monitoring/state/reference.parquet"
    cur = PROJECT_DIR / "monitoring/state/current.parquet"
    out = PROJECT_DIR / "reports/drift"

    if not ref.exists() or not cur.exists():
        # No prior data — treat as drifted so the rest of the DAG runs once
        context["ti"].xcom_push(key="drift_share", value=1.0)
        return True

    exit_code = run_drift_check(ref, cur, out, fail_share_threshold=DRIFT_THRESHOLD)
    drift_share = 1.0 if exit_code else 0.0  # exit code 1 = exceeded threshold
    context["ti"].xcom_push(key="drift_share", value=drift_share)

    is_forced = context["dag_run"].conf.get("force", False) if context["dag_run"].conf else False
    return is_forced or drift_share > 0


def build_slack_message(**context) -> str:
    drift_share = context["ti"].xcom_pull(task_ids="drift_check", key="drift_share")
    return (
        ":white_check_mark: *credit-default retrain complete*\n"
        f"• drift share = {drift_share}\n"
        f"• run = {context['run_id']}\n"
        "• new staging model registered; canary roll-out triggered."
    )


with DAG(
    dag_id="credit_default_retrain",
    description="Weekly + drift-triggered retraining of credit-default model",
    schedule_interval="0 2 * * 0",  # Sunday 02:00 UTC
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["mlops", "credit-default"],
) as dag:

    drift_check = ShortCircuitOperator(
        task_id="drift_check",
        python_callable=check_drift,
        provide_context=True,
    )

    ingest = BashOperator(
        task_id="ingest",
        bash_command=f"cd {PROJECT_DIR} && python -m src.data.ingest",
    )

    validate = BashOperator(
        task_id="validate",
        bash_command=f"cd {PROJECT_DIR} && python -m src.data.validate",
    )

    features = BashOperator(
        task_id="features",
        bash_command=f"cd {PROJECT_DIR} && python -m src.features.build",
    )

    train = BashOperator(
        task_id="train",
        bash_command=f"cd {PROJECT_DIR} && python -m src.models.train",
        execution_timeout=timedelta(hours=3),
    )

    evaluate = BashOperator(
        task_id="evaluate",
        bash_command=f"cd {PROJECT_DIR} && python -m src.models.evaluate",
    )

    register = BashOperator(
        task_id="register",
        bash_command=f"cd {PROJECT_DIR} && python -m src.models.register",
    )

    # Annotate the Argo Rollout to roll out the new image.
    # Argo Rollouts watches its target Deployment/Rollout for spec changes;
    # we patch the image tag and Argo handles canary progression.
    trigger_canary = BashOperator(
        task_id="trigger_canary",
        bash_command=(
            "kubectl -n credit-default set image "
            "rollout/credit-default-api api={{ var.value.api_image_repository }}:"
            "{{ var.value.api_image_tag_staging }}"
        ),
    )

    notify_slack = SlackWebhookOperator(
        task_id="notify_slack",
        slack_webhook_conn_id=SLACK_CONN_ID,
        message="{{ ti.xcom_pull(task_ids='build_message') }}",
        trigger_rule="all_done",
    )

    build_message = PythonOperator(
        task_id="build_message",
        python_callable=build_slack_message,
        provide_context=True,
        trigger_rule="all_done",
    )

    drift_check >> ingest >> validate >> features >> train >> evaluate >> register
    register >> trigger_canary >> build_message >> notify_slack
