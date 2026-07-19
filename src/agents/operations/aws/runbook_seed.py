"""
CloudFormation custom resource handler for seeding built-in runbooks.
"""

from __future__ import annotations

import os
from typing import Any

import boto3
import structlog

from src.agents.runbooks.catalog import builtin_runbook_items
from src.agents.runbooks.schema import validate_runbook

logger = structlog.get_logger(__name__)

_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
_DYNAMO = boto3.resource("dynamodb", region_name=_REGION)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    request_type = event.get("RequestType", "Create")
    props = event.get("ResourceProperties", {})
    table_name = props.get("TableName") or os.getenv("RUNBOOK_TABLE", "incident-runbooks")
    catalog_version = props.get("CatalogVersion", "v1")

    logger.info(
        "runbook_seed.start",
        request_type=request_type,
        table_name=table_name,
        catalog_version=catalog_version,
    )

    if request_type in {"Create", "Update"}:
        count = _seed_runbooks(table_name)
        physical_id = f"runbook-seed-{catalog_version}"
        logger.info("runbook_seed.done", seeded_count=count, physical_id=physical_id)
        return {
            "PhysicalResourceId": physical_id,
            "Data": {
                "SeededCount": count,
                "TableName": table_name,
            },
        }

    physical_id = event.get("PhysicalResourceId", f"runbook-seed-{catalog_version}")
    logger.info("runbook_seed.delete", physical_id=physical_id)
    return {"PhysicalResourceId": physical_id}


def _seed_runbooks(table_name: str) -> int:
    table = _DYNAMO.Table(table_name)
    seeded = 0
    for item in builtin_runbook_items():
        problems = validate_runbook(item, require_alarm_name=True)
        if problems:
            logger.error(
                "runbook_seed.invalid_item",
                runbook_id=item.get("runbook_id"),
                problems=problems,
            )
            continue
        table.put_item(Item=item)
        seeded += 1
    return seeded
