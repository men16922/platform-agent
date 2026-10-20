"""Keep acquired state/recovery facts separate from the model's interpretation."""
from __future__ import annotations

from typing import Any


REASONS = {
    "observation_time_outside_window_or_unknown": "Observation time is unknown or outside the requested window.",
    "deployment_generation_not_observed": "The deployment controller has not observed this generation.",
    "positive_desired_replicas_not_established": "The desired replica count is not established.",
    "current_rollout_complete_no_rollback_need_established": "The current rollout is complete; these observations do not establish a need to roll back.",
    "current_revision_failure_not_established": "A failure of the current revision is not established.",
    "previous_revision_template_not_established": "A specific previous revision and its template are not established.",
    "previous_revision_health_not_established": "The previous revision's health is not established.",
}


def model_completion(messages: list[Any], text: str) -> dict:
    """Record transport completion without treating it as semantic verification."""
    from pydantic_ai.messages import ModelResponse, ToolCallPart
    responses = [m for m in messages if isinstance(m, ModelResponse)]
    reason = responses[-1].finish_reason if responses else None
    complete = reason == "stop" and responses[-1].state == "complete"
    # Pydantic AI also uses zero-valued RequestUsage when the provider did not
    # report usage. Preserve positive provider counters; do not turn absent or
    # ambiguous zero counters into a measured zero-cost inference.
    known_usage = bool(responses) and all(r.usage.input_tokens > 0 and r.usage.output_tokens > 0 for r in responses)
    return {"status": "complete" if complete else "unknown" if reason is None else "incomplete",
            "finish_reason": reason, "text": text, "semantic_verified": False,
            "model_responses": len(responses),
            "tool_call_attempts": sum(isinstance(part, ToolCallPart) for response in responses for part in response.parts),
            "token_usage": {"status": "reported" if known_usage else "not_established",
                            "input_tokens": sum(r.usage.input_tokens for r in responses) if known_usage else None,
                            "output_tokens": sum(r.usage.output_tokens for r in responses) if known_usage else None}}


def inspection_report(steps: list[dict]) -> list[dict] | None:
    """Project facts only for a run composed entirely of known read-only tools.

    This is a presentation boundary, not a substitute for a read-only capability
    or an authorization check. The original tool results remain in the trace.
    """
    from src.agents.ai.local_deployer import AGENT_TOOL_CATALOG
    read_tools = {t.name for t in AGENT_TOOL_CATALOG if t.category == "Investigate"}
    if not steps or any(step.get("tool") not in read_tools for step in steps):
        return None
    reports = []
    for step in steps:
        if step.get("tool") != "describe_deployment":
            continue
        result, args = step.get("result"), step.get("args", {})
        evidence = result.get("evidence") if isinstance(result, dict) else None
        # Older describe results have no structured facts; do not fabricate a
        # report from their human-readable text or the model's final response.
        if not isinstance(evidence, dict):
            continue
        target = evidence.get("target", {})
        bound = (target.get("deployment") == args.get("deployment")
                 and target.get("namespace") == args.get("namespace", "default"))
        if not bound or not isinstance(evidence.get("recovery"), dict):
            reports.append({"deployment": args.get("deployment", "Unknown deployment"),
                            "namespace": args.get("namespace", "default"), "available": False,
                            "error": evidence.get("error", "Structured observation could not be bound to the requested target.")})
            continue
        current, previous, recovery = evidence.get("current") or {}, evidence.get("previous") or {}, evidence["recovery"]
        reports.append({
            "available": True, "deployment": target["deployment"], "namespace": target["namespace"],
            "context": target.get("context"), "uid": target.get("uid"), "observed_at": evidence.get("as_of"),
            "current_revision": evidence.get("revision"), "previous_revision": previous.get("revision"),
            "rollout_complete": evidence.get("rollout_complete") is True,
            "desired_replicas": evidence.get("desired_replicas"), "rollout_counts": evidence.get("rollout_counts", {}),
            "current_health": current.get("health_basis", "not_established"),
            "previous_health": previous.get("health_basis", "not_established"),
            "recovery_status": recovery.get("status", "not_established"),
            "candidate_revision": recovery.get("candidate_revision"),
            "recovery_reasons": [REASONS.get(reason, "Additional recovery evidence is missing.")
                                 for reason in recovery.get("reasons", [])],
            "execution_authorized": False, "sources": evidence.get("sources", []), "limits": evidence.get("limits", []),
        })
    return reports or None


def inspection_summary(reports: list[dict]) -> str:
    """A durable factual summary for readers outside the chat component."""
    parts = []
    for report in reports:
        title = f"{report['namespace']}/{report['deployment']}"
        if not report["available"]:
            parts.append(f"{title}: structured observation unavailable. Recovery is not established.")
            continue
        health = ("Kubernetes readiness observed; external service health not verified"
                  if report["current_health"] == "kubernetes_readiness" else "Application health not established")
        recovery = (f"Revision {report['candidate_revision']} is a recovery review candidate; execution not authorized"
                    if report["recovery_status"] == "review_candidate" else "Recovery candidate not established")
        parts.append(f"{title}: revision {report['current_revision']}; rollout "
                     f"{'complete' if report['rollout_complete'] else 'not confirmed complete'}. "
                     f"{health}. {recovery}. Observed at {report['observed_at']}.")
    return "\n\n".join(parts)
