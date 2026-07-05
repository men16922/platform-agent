"""
Deployment Agent — smoke test planning helpers.
"""

from __future__ import annotations

from typing import Any


def build_smoke_test_plan(deployment: dict[str, Any]) -> dict[str, Any]:
    service_name = deployment["service_name"]
    base_url = deployment["base_url"].rstrip("/")
    endpoints = deployment.get("core_endpoints", [])

    checks = [
        {"name": "health", "method": "GET", "url": f"{base_url}{deployment.get('health_path', '/healthz')}"},
    ]
    for endpoint in endpoints:
        checks.append({"name": endpoint["name"], "method": endpoint.get("method", "GET"), "url": f"{base_url}{endpoint['path']}"})

    return {
        "service_name": service_name,
        "checks": checks,
        "success_threshold": 1.0,
    }


def summarise_smoke_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    passed = [result for result in results if result.get("status") == "passed"]
    failed = [result for result in results if result.get("status") != "passed"]
    return {
        "passed": len(passed),
        "failed": len(failed),
        "should_continue": len(failed) == 0,
        "failed_checks": [result.get("name", "unknown") for result in failed],
    }
