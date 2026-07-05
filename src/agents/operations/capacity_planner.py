"""
Operations Agent — monthly capacity planning helpers.
"""

from __future__ import annotations

from typing import Any


def analyze_service_capacity(
    service_name: str,
    samples: list[dict[str, float]],
    *,
    monthly_cost_usd: float | None = None,
) -> dict[str, Any]:
    if not samples:
        raise ValueError("samples cannot be empty")

    avg_cpu = _average(sample.get("cpu_utilization", 0.0) for sample in samples)
    peak_cpu = max(sample.get("cpu_utilization", 0.0) for sample in samples)
    avg_memory = _average(sample.get("memory_utilization", 0.0) for sample in samples)
    peak_memory = max(sample.get("memory_utilization", 0.0) for sample in samples)

    cpu_trend = _trend_delta(samples, "cpu_utilization")
    memory_trend = _trend_delta(samples, "memory_utilization")
    recommendation = _recommend_action(avg_cpu, peak_cpu, avg_memory, peak_memory, cpu_trend, memory_trend)

    return {
        "service_name": service_name,
        "sample_count": len(samples),
        "avg_cpu_utilization": round(avg_cpu, 2),
        "peak_cpu_utilization": round(peak_cpu, 2),
        "avg_memory_utilization": round(avg_memory, 2),
        "peak_memory_utilization": round(peak_memory, 2),
        "cpu_trend_delta": round(cpu_trend, 2),
        "memory_trend_delta": round(memory_trend, 2),
        "monthly_cost_usd": round(monthly_cost_usd, 2) if monthly_cost_usd is not None else None,
        "recommendation": recommendation,
    }


def build_monthly_capacity_report(service_analyses: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = sorted(
        service_analyses,
        key=lambda analysis: (
            _recommendation_rank(analysis["recommendation"]),
            analysis.get("peak_cpu_utilization", 0.0),
            analysis.get("peak_memory_utilization", 0.0),
        ),
        reverse=True,
    )
    return {
        "report_type": "monthly_capacity",
        "service_count": len(service_analyses),
        "priority_services": [analysis["service_name"] for analysis in ranked[:3]],
        "services": ranked,
    }


def _recommend_action(
    avg_cpu: float,
    peak_cpu: float,
    avg_memory: float,
    peak_memory: float,
    cpu_trend: float,
    memory_trend: float,
) -> str:
    if peak_cpu >= 85 or peak_memory >= 85 or cpu_trend >= 15 or memory_trend >= 15:
        return "scale_up"
    if avg_cpu <= 35 and avg_memory <= 40 and peak_cpu <= 55 and peak_memory <= 60:
        return "optimize_cost"
    return "observe"


def _average(values: Any) -> float:
    items = list(values)
    return sum(items) / len(items)


def _trend_delta(samples: list[dict[str, float]], key: str) -> float:
    midpoint = max(1, len(samples) // 2)
    first_half = samples[:midpoint]
    second_half = samples[midpoint:]
    if not second_half:
        second_half = first_half
    return _average(sample.get(key, 0.0) for sample in second_half) - _average(
        sample.get(key, 0.0) for sample in first_half
    )


def _recommendation_rank(recommendation: str) -> int:
    ranking = {
        "scale_up": 3,
        "observe": 2,
        "optimize_cost": 1,
    }
    return ranking.get(recommendation, 0)
