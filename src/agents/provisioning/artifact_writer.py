"""
Provisioning Agent — CDK artifact writer.

Persists generated CDK TypeScript artifacts to S3 and updates the
provisioning plan record so downstream systems can retrieve the bundle.
"""

from __future__ import annotations

import io
import os
import time
import zipfile
from typing import Any

import boto3
import structlog

logger = structlog.get_logger(__name__)

_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
_PLAN_TABLE = os.getenv("PROVISIONING_TABLE", "provisioning-plans")
_ARTIFACT_BUCKET = os.getenv("PROVISIONING_ARTIFACT_BUCKET", "")
_ARTIFACT_PREFIX = os.getenv("PROVISIONING_ARTIFACT_PREFIX", "plans")

_S3 = boto3.client("s3", region_name=_REGION)
_DYNAMO = boto3.resource("dynamodb", region_name=_REGION)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Write the generated CDK artifact bundle to S3 and annotate the plan."""

    plan_id = event["plan_id"]
    artifact = event["cdk_artifact"]
    blueprint = event["blueprint"]
    service_name = blueprint["service_name"]

    if not _ARTIFACT_BUCKET:
        raise ValueError("PROVISIONING_ARTIFACT_BUCKET is required")

    archive_key = _build_archive_key(plan_id, service_name)
    archive_body = _build_archive_bytes(artifact)

    log = logger.bind(plan_id=plan_id, bucket=_ARTIFACT_BUCKET, key=archive_key)
    log.info("provisioning.artifact_writer.start")

    _S3.put_object(
        Bucket=_ARTIFACT_BUCKET,
        Key=archive_key,
        Body=archive_body,
        ContentType="application/zip",
        Metadata={
            "plan-id": plan_id,
            "service-name": service_name,
            "platform": blueprint["platform"],
        },
    )

    artifact_bundle = {
        "bucket": _ARTIFACT_BUCKET,
        "key": archive_key,
        "s3_uri": f"s3://{_ARTIFACT_BUCKET}/{archive_key}",
        "file_count": len(artifact.get("files", [])),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _update_plan(plan_id, artifact_bundle)

    log.info("provisioning.artifact_writer.done", file_count=artifact_bundle["file_count"])
    return {
        **event,
        "artifact_bundle": artifact_bundle,
        "status": "artifact_ready",
    }


def _build_archive_key(plan_id: str, service_name: str) -> str:
    normalized_service = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in service_name)
    return f"{_ARTIFACT_PREFIX.rstrip('/')}/{plan_id}/{normalized_service}-cdk-artifact.zip"


def _build_archive_bytes(artifact: dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in artifact.get("files", []):
            archive.writestr(file["path"], file["content"])
    return buffer.getvalue()


def _update_plan(plan_id: str, artifact_bundle: dict[str, Any]) -> None:
    table = _DYNAMO.Table(_PLAN_TABLE)
    table.update_item(
        Key={"plan_id": plan_id},
        UpdateExpression=(
            "SET #status = :status, artifact_bucket = :bucket, artifact_key = :key, "
            "artifact_s3_uri = :uri, artifact_file_count = :file_count, artifact_updated_at = :updated_at"
        ),
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": "artifact_ready",
            ":bucket": artifact_bundle["bucket"],
            ":key": artifact_bundle["key"],
            ":uri": artifact_bundle["s3_uri"],
            ":file_count": artifact_bundle["file_count"],
            ":updated_at": artifact_bundle["updated_at"],
        },
    )
