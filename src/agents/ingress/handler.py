"""
Generic ingress handler for provisioning/deployment requests.

Accepts:
  1. Lambda Function URL / API Gateway style HTTP events with a JSON body
  2. Direct Lambda invocation payloads

Normalises the request into a custom EventBridge event so the runtime router can
apply the same routing logic regardless of the original source.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any

import boto3
import structlog

logger = structlog.get_logger(__name__)

_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
_EVENT_BUS_NAME = os.getenv("EVENT_BUS_NAME", "default")
_DEFAULT_SOURCE = os.getenv("INGRESS_EVENT_SOURCE", "platform-agent.api")

_EVENTS = boto3.client("events", region_name=_REGION)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    request = _normalise_request(event)

    logger.info(
        "ingress.publish.start",
        source=request["source"],
        detail_type=request["detail_type"],
        event_bus=_EVENT_BUS_NAME,
    )

    response = _EVENTS.put_events(
        Entries=[
            {
                "EventBusName": _EVENT_BUS_NAME,
                "Source": request["source"],
                "DetailType": request["detail_type"],
                "Detail": json.dumps(request["detail"]),
            }
        ]
    )

    failed = response.get("FailedEntryCount", 0)
    if failed:
        entry = (response.get("Entries") or [{}])[0]
        raise RuntimeError(f"EventBridge publish failed: {entry.get('ErrorCode')} {entry.get('ErrorMessage')}")

    result = {
        "accepted": True,
        "source": request["source"],
        "detail_type": request["detail_type"],
        "event_id": (response.get("Entries") or [{}])[0].get("EventId"),
        "event_bus": _EVENT_BUS_NAME,
    }
    logger.info("ingress.publish.done", event_id=result["event_id"])

    if _is_http_event(event):
        return _http_response(202, result)
    return result


def _normalise_request(event: dict[str, Any]) -> dict[str, Any]:
    payload = _http_payload(event) if _is_http_event(event) else event
    if not isinstance(payload, dict):
        raise ValueError("Ingress payload must be a JSON object")

    detail = payload.get("detail")
    if not isinstance(detail, dict):
        detail = {
            key: value
            for key, value in payload.items()
            if key not in {"source", "detail-type", "detail_type", "pipeline"}
        }

    pipeline = str(payload.get("pipeline") or detail.get("pipeline") or "").strip().lower()
    if pipeline and "pipeline" not in detail:
        detail["pipeline"] = pipeline

    detail_type = payload.get("detail-type") or payload.get("detail_type") or _detail_type_from_pipeline(pipeline)
    if not detail_type:
        raise ValueError("Ingress payload must specify detail-type/detail_type or pipeline")

    return {
        "source": str(payload.get("source") or _DEFAULT_SOURCE),
        "detail_type": str(detail_type),
        "detail": detail,
    }


def _detail_type_from_pipeline(pipeline: str) -> str | None:
    if pipeline in {"provisioning", "provision"}:
        return "Provisioning Request"
    if pipeline in {"deployment", "deployment_validation", "validate_deployment"}:
        return "Deployment Validation Request"
    return None


def _is_http_event(event: dict[str, Any]) -> bool:
    request_context = event.get("requestContext", {})
    return isinstance(request_context, dict) and "http" in request_context


def _http_payload(event: dict[str, Any]) -> dict[str, Any]:
    body = event.get("body", "")
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    if not body:
        return {}
    return json.loads(body)


def _http_response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
