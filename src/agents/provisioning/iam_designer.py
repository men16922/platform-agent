"""
Provisioning Agent — least-privilege IAM planning helpers.
"""

from __future__ import annotations

from typing import Any


_DEPENDENCY_TEMPLATES: dict[str, dict[str, Any]] = {
    "cloudwatch": {
        "actions": ["cloudwatch:PutMetricData"],
        "resources": ["*"],
    },
    "logs_write": {
        "actions": ["logs:CreateLogStream", "logs:PutLogEvents"],
        "resources": ["arn:aws:logs:*:*:log-group:/aws/*"],
    },
    "xray_write": {
        "actions": ["xray:PutTraceSegments", "xray:PutTelemetryRecords"],
        "resources": ["*"],
    },
    "s3_read": {
        "actions": ["s3:GetObject", "s3:ListBucket"],
        "resources": ["arn:aws:s3:::example-bucket", "arn:aws:s3:::example-bucket/*"],
    },
    "dynamodb_rw": {
        "actions": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query"],
        "resources": ["arn:aws:dynamodb:*:*:table/example-table"],
    },
    "sqs_producer": {
        "actions": ["sqs:SendMessage"],
        "resources": ["arn:aws:sqs:*:*:example-queue"],
    },
}


def build_iam_plan(
    service_name: str,
    dependencies: list[str] | None = None,
    *,
    include_baseline_observability: bool = True,
) -> dict[str, Any]:
    """
    Build a least-privilege IAM role plan from dependency hints.

    The output is intentionally close to what CDK can consume:
      {
        "role_name": "...",
        "managed_policies": [...],
        "inline_statements": [{"actions": [...], "resources": [...]}],
      }
    """
    dependencies = list(dependencies or [])
    statements: list[dict[str, Any]] = []

    if include_baseline_observability:
        dependencies = ["logs_write", "cloudwatch", "xray_write", *dependencies]

    seen: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
    for dependency in dependencies:
        template = _DEPENDENCY_TEMPLATES.get(dependency)
        if not template:
            raise ValueError(f"Unknown dependency template: {dependency}")
        key = (tuple(template["actions"]), tuple(template["resources"]))
        if key in seen:
            continue
        seen.add(key)
        statements.append(
            {
                "sid": f"{dependency.title().replace('_', '')}Access",
                "actions": template["actions"],
                "resources": template["resources"],
            }
        )

    return {
        "role_name": f"{service_name.strip().lower().replace(' ', '-')}-service-role",
        "managed_policies": ["service-role/AWSLambdaBasicExecutionRole"],
        "inline_statements": statements,
        "notes": [
            "Replace example ARNs with stack-specific resources before deployment.",
            "Keep wildcard resources only for telemetry APIs that require them.",
        ],
    }
