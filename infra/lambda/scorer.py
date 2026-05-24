"""Lambda handler: batch-score loan applications dropped into S3.

Trigger: s3:ObjectCreated on s3://<DATA_BUCKET>/batch/incoming/*.csv
Action:  read the CSV, invoke the SageMaker endpoint per row, write the scored
         output to s3://<ARTIFACTS_BUCKET>/batch/scored/<basename>.json
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
from urllib.parse import unquote_plus

import boto3

log = logging.getLogger()
log.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

S3 = boto3.client("s3")
SAGEMAKER = boto3.client("sagemaker-runtime")

ARTIFACTS_BUCKET = os.environ["ARTIFACTS_BUCKET"]
SAGEMAKER_ENDPOINT = os.environ["SAGEMAKER_ENDPOINT"]


def handler(event: dict, context) -> dict:
    results: list[dict] = []
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        log.info("scorer.start", extra={"bucket": bucket, "key": key})

        obj = S3.get_object(Bucket=bucket, Key=key)
        body = obj["Body"].read().decode("utf-8")

        scored = list(_score_csv(body))

        out_key = f"batch/scored/{key.split('/')[-1]}.json"
        S3.put_object(
            Bucket=ARTIFACTS_BUCKET,
            Key=out_key,
            Body=json.dumps(scored).encode("utf-8"),
            ContentType="application/json",
        )
        log.info(
            "scorer.done",
            extra={"rows": len(scored), "out_bucket": ARTIFACTS_BUCKET, "out_key": out_key},
        )
        results.append({"input": f"s3://{bucket}/{key}", "output_rows": len(scored)})

    return {"processed": results}


def _score_csv(body: str):
    reader = csv.DictReader(io.StringIO(body))
    for row in reader:
        payload = {"applications": [_normalise_row(row)]}
        response = SAGEMAKER.invoke_endpoint(
            EndpointName=SAGEMAKER_ENDPOINT,
            ContentType="application/json",
            Body=json.dumps(payload).encode("utf-8"),
        )
        result = json.loads(response["Body"].read())
        yield {"input": row, "prediction": result["predictions"][0]}


def _normalise_row(row: dict) -> dict:
    """Best-effort coercion of CSV string fields to the API's typed schema."""
    typed: dict = {}
    int_fields = {"sex", "education", "marriage", "age",
                  "pay_0", "pay_2", "pay_3", "pay_4", "pay_5", "pay_6"}
    for k, v in row.items():
        k = k.strip().lower()
        if k in int_fields:
            typed[k] = int(v)
        else:
            typed[k] = float(v)
    return typed
