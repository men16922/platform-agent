"""
Provisioning Agent — CDK blueprint helpers.

This module does not emit TypeScript directly yet. Instead, it produces a
normalized blueprint that a future Codex codegen step can turn into CDK stacks.
"""

from __future__ import annotations

from typing import Any


def build_service_blueprint(request: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize a Day 1 provisioning request into a CDK-friendly blueprint.

    Required input:
      - service_name

    Optional input:
      - platform: eks | lambda
      - exposure: internal | public
      - port
      - desired_count
      - cpu
      - memory
      - environments
      - integrations
    """
    service_name = _slug(request["service_name"])
    platform = _normalise_platform(request.get("platform", "eks"))
    exposure = request.get("exposure", "internal")
    port = int(request.get("port", 8080 if platform == "eks" else 443))
    desired_count = int(request.get("desired_count", 2 if platform == "eks" else 1))

    blueprint = {
        "service_name": service_name,
        "stack_name": f"{_pascal(service_name)}ServiceStack",
        "platform": platform,
        "runtime": request.get("runtime", "container" if platform == "eks" else "python"),
        "network": {
            "exposure": exposure,
            "port": port,
            "health_check_path": request.get("health_check_path", _default_health_check(platform)),
        },
        "capacity": {
            "desired_count": desired_count,
            "cpu": int(request.get("cpu", 512 if platform == "eks" else 256)),
            "memory": int(request.get("memory", 1024 if platform == "eks" else 512)),
        },
        "environments": request.get("environments", ["dev", "prod"]),
        "integrations": sorted(set(request.get("integrations", ["cloudwatch"]))),
        "resources": _default_resources(platform, exposure),
        "deployment_strategy": {
            "type": "rolling" if platform == "eks" else "linear",
            "requires_canary_analysis": True,
        },
        "guardrails": [
            "least_privilege_iam",
            "cloudwatch_dashboard",
            "alarm_pack",
            "deployment_health_checks",
        ],
    }
    return blueprint


def _normalise_platform(value: str) -> str:
    lowered = value.strip().lower()
    if lowered in {"eks", "kubernetes", "k8s"}:
        return "eks"
    if lowered in {"lambda", "serverless"}:
        return "lambda"
    raise ValueError(f"Unsupported platform: {value}")


def _default_resources(platform: str, exposure: str) -> dict[str, Any]:
    base = {
        "cloudwatch_dashboard": True,
        "alarm_pack": True,
        "log_retention_days": 30,
    }
    if platform == "eks":
        base.update(
            {
                "compute": "fargate_profile",
                "load_balancer": "alb" if exposure == "public" else "internal-alb",
                "autoscaling": {"min": 2, "max": 6},
            }
        )
    else:
        base.update(
            {
                "compute": "lambda",
                "reserved_concurrency": 10 if exposure == "public" else 2,
                "function_url": exposure == "public",
            }
        )
    return base


def _default_health_check(platform: str) -> str:
    return "/healthz" if platform == "eks" else "/"


def _slug(value: str) -> str:
    return value.strip().lower().replace(" ", "-").replace("_", "-")


def _pascal(value: str) -> str:
    return "".join(part.capitalize() for part in value.replace("_", "-").split("-") if part)
