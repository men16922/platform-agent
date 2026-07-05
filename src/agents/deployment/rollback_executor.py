"""
Deployment Rollback Executor — Lambda handler.

Turns a rollback decision into either:
  1. An SSM Automation execution when a rollback document is configured, or
  2. A concrete manual rollback plan when the deployment request did not supply
     an automation target.
"""

from __future__ import annotations

import os
from typing import Any

import boto3
import structlog

logger = structlog.get_logger(__name__)

_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
_SSM = boto3.client("ssm", region_name=_REGION)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    deployment_id = event.get("deployment_id", "unknown")
    service_name = event.get("service_name", "unknown")
    version = event.get("version", "unknown")
    execution_context = event.get("execution_context", {})
    platform = str(execution_context.get("platform", "generic")).lower()
    target_version = _target_version(execution_context)
    document_name = str(execution_context.get("rollback_document_name", "")).strip()

    log = logger.bind(
        deployment_id=deployment_id,
        service_name=service_name,
        version=version,
        platform=platform,
        target_version=target_version,
    )
    log.info("deployment.rollback.start")

    if document_name:
        parameters = _ssm_parameters(event, execution_context, target_version)
        response = _SSM.start_automation_execution(
            DocumentName=document_name,
            DocumentVersion="$DEFAULT",
            Parameters=parameters,
        )
        execution_id = response["AutomationExecutionId"]
        log.info("deployment.rollback.started", document_name=document_name, execution_id=execution_id)
        return {
            **event,
            "rollback_mode": "ssm_automation",
            "rollback_status": "started",
            "rollback_document_name": document_name,
            "rollback_target_version": target_version,
            "rollback_execution_id": execution_id,
            "rollback_parameters": parameters,
        }

    rollback_plan = _manual_plan(event, execution_context, target_version)
    log.info("deployment.rollback.manual", rollback_plan=rollback_plan)
    return {
        **event,
        "rollback_mode": "manual",
        "rollback_status": "manual_intervention_required",
        "rollback_target_version": target_version,
        "rollback_execution_id": None,
        "rollback_plan": rollback_plan,
    }


def _target_version(execution_context: dict[str, Any]) -> str:
    return str(
        execution_context.get("rollback_target_version")
        or execution_context.get("stable_version")
        or execution_context.get("previous_version")
        or "latest-known-good"
    )


def _ssm_parameters(
    event: dict[str, Any],
    execution_context: dict[str, Any],
    target_version: str,
) -> dict[str, list[str]]:
    parameters = _normalise_parameter_map(execution_context.get("rollback_parameters", {}))
    defaults = {
        "ServiceName": event.get("service_name"),
        "DeploymentId": event.get("deployment_id"),
        "SourceVersion": event.get("version"),
        "TargetVersion": target_version,
        "Reason": event.get("rollout_reason"),
        "Platform": execution_context.get("platform"),
        "DeploymentEnvironment": execution_context.get("deployment_environment"),
        "ClusterName": execution_context.get("cluster_name"),
        "Namespace": execution_context.get("namespace"),
        "WorkloadName": execution_context.get("workload_name"),
        "FunctionName": execution_context.get("function_name"),
        "AliasName": execution_context.get("alias_name"),
    }
    for key, value in defaults.items():
        if value and key not in parameters:
            parameters[key] = [str(value)]
    return parameters


def _normalise_parameter_map(raw: Any) -> dict[str, list[str]]:
    if not isinstance(raw, dict):
        return {}

    normalized: dict[str, list[str]] = {}
    for key, value in raw.items():
        if value is None:
            continue
        if isinstance(value, list):
            normalized[key] = [str(item) for item in value if item is not None]
        else:
            normalized[key] = [str(value)]
    return normalized


def _manual_plan(
    event: dict[str, Any],
    execution_context: dict[str, Any],
    target_version: str,
) -> dict[str, Any]:
    platform = str(execution_context.get("platform", "generic")).lower()
    service_name = event.get("service_name", "unknown")
    version = event.get("version", "unknown")
    reason = event.get("rollout_reason", "rollback requested")

    next_actions = [
        f"Confirm rollback target `{target_version}` for `{service_name}`.",
        f"Review rollout regression reason: {reason}.",
    ]
    suggested_command = None

    if platform == "eks" and execution_context.get("workload_name"):
        namespace = execution_context.get("namespace", "default")
        workload = execution_context["workload_name"]
        suggested_command = f"kubectl rollout undo deployment/{workload} --namespace {namespace}"
        next_actions.append("Use the rollout undo command or equivalent GitOps revert.")
    elif platform == "lambda" and execution_context.get("function_name"):
        alias_name = execution_context.get("alias_name", "live")
        function_name = execution_context["function_name"]
        suggested_command = (
            f"aws lambda update-alias --function-name {function_name} --name {alias_name} "
            f"--function-version {target_version}"
        )
        next_actions.append("Shift the serving alias back to the last known-good version.")
    else:
        next_actions.append("Execute the platform team's standard rollback runbook.")

    return {
        "platform": platform,
        "service_name": service_name,
        "source_version": version,
        "target_version": target_version,
        "reason": reason,
        "suggested_command": suggested_command,
        "next_actions": next_actions,
        "rollback_context": execution_context.get("rollback_context", {}),
    }
