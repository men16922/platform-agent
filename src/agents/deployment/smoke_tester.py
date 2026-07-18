"""
Deployment Agent — smoke test planning helpers.
"""

from __future__ import annotations

from typing import Any


def build_smoke_test_plan(deployment: dict[str, Any]) -> dict[str, Any]:
    service_name = deployment.get("service_name", "unknown")
    # base_url is optional: dashboard-triggered validation runs carry no endpoint,
    # and a plan with no checks passes vacuously (same as no_canary_data_available).
    base_url = (deployment.get("base_url") or "").rstrip("/")
    endpoints = deployment.get("core_endpoints", [])

    checks: list[dict[str, Any]] = []
    if base_url:
        checks.append(
            {"name": "health", "method": "GET", "url": f"{base_url}{deployment.get('health_path', '/healthz')}"}
        )
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
