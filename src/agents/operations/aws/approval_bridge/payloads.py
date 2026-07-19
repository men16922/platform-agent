"""Approval payload helpers shared by the bridge handler, store, and Slack modules."""

from __future__ import annotations

from typing import Any


def _normalise_decision(decision: str) -> str:
    if decision in {"approve", "approved", "auto_approve"}:
        return "approve"
    return "reject"


def _request_kind(payload: dict[str, Any]) -> str:
    value = str(payload.get("request_kind", "incident")).strip().lower()
    return value or "incident"


def _request_subject(payload: dict[str, Any]) -> str:
    return str(payload.get("request_subject") or payload.get("alarm_name") or "unknown")


def _summary_text(payload: dict[str, Any]) -> str:
    return str(payload.get("request_summary") or payload.get("root_cause") or "No summary provided.")


def _summary_heading(payload: dict[str, Any]) -> str:
    if _request_kind(payload) == "incident":
        return "Root Cause"
    return "Request Summary"


def _header_text(payload: dict[str, Any]) -> str:
    severity = payload.get("severity", "P2")
    request_kind = _request_kind(payload)
    subject = _request_subject(payload)
    label = {
        "incident": "Approval gate",
        "provisioning": "Provisioning approval",
        "deployment": "Deployment approval",
    }.get(request_kind, "Approval request")
    return f"[{severity}] {label}: {subject}"
