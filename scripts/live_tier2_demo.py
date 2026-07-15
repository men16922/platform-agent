"""Live demonstration of Tier 2 #2 (self-consistency) + Tier 1 reconciliation gate
against the real local MLX Qwen model — not stubs.

Exercises the SHIPPED code paths:
  - src.agents.ai.orchestration.route_with_self_consistency  (with a real LLM sampler)
  - src.agents.ai.reconciliation.reconcile / apply_gate      (on real LLM analysis)

Requires a running MLX-LM endpoint (default http://127.0.0.1:18090/v1).
Run: python scripts/live_tier2_demo.py
"""

from __future__ import annotations

import json
import os
from collections import Counter
from urllib import request

from src.agents.ai.orchestration import route_with_self_consistency
from src.agents.ai.reconciliation import apply_gate, reconcile
from src.agents.ai.supervisor import AgentRole, RouteDecision
from src.agents.models import (
    AlarmContext,
    AnalyzerOutput,
    DetectorOutput,
    RemediationMode,
    Severity,
)

ENDPOINT = os.getenv("ONPREM_LLM_ENDPOINT", "http://127.0.0.1:18090/v1").rstrip("/")
MODEL = os.getenv("ONPREM_LLM_MODEL", "mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit")


def _chat(system: str, user: str, *, temperature: float, max_tokens: int = 64) -> str:
    body = {
        "model": MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    req = request.Request(
        f"{ENDPOINT}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"].strip()


# --- Part A: self-consistency routing with a REAL LLM sampler -----------------

_ROUTER_SYSTEM = (
    "You are a request router for a platform operations agent. Classify the user's "
    "request into EXACTLY ONE role and reply with only that single word:\n"
    "- provision : create/tear down infrastructure or clusters (terraform, ansible, IaC)\n"
    "- deploy    : build, ship, roll back, or validate an application\n"
    "- kagent    : read-only investigation/diagnosis (logs, pod status, metrics, why is X failing)\n"
    "Reply with ONLY one word: provision, deploy, or kagent."
)


def llm_sampler(instruction: str) -> RouteDecision:
    """A real LLM classifier. High temperature → the model genuinely varies across
    samples, which is exactly what self-consistency is meant to reconcile."""
    text = _chat(_ROUTER_SYSTEM, instruction, temperature=1.0, max_tokens=8).lower()
    for role in (AgentRole.PROVISION, AgentRole.KAGENT, AgentRole.DEPLOY):
        if role.value in text:
            return RouteDecision(role, f"llm:{text[:30]!r}")
    return RouteDecision(AgentRole.DEPLOY, f"llm-unparsed:{text[:30]!r}")


def demo_self_consistency() -> None:
    print("\n" + "=" * 78)
    print("PART A — Tier 2 #2: self-consistency routing (REAL MLX Qwen sampler, temp=1.0)")
    print("=" * 78)
    cases = [
        ("clear intent", "Deploy orders-api v1.8.0 to the production cluster and confirm it is healthy."),
        ("ambiguous intent", "The orders cluster looks off — take care of it."),
    ]
    for label, instruction in cases:
        print(f"\n[{label}] {instruction!r}")
        # Sample the REAL model 5x through the shipped self-consistency router.
        samples: list[RouteDecision] = []

        def sampler(i: str, _bucket=samples) -> RouteDecision:
            d = llm_sampler(i)
            _bucket.append(d)
            return d

        consensus = route_with_self_consistency(
            instruction, sampler=sampler, samples=5, min_agreement=0.6
        )
        votes = Counter(d.role.value for d in samples)
        print(f"  raw LLM votes (5 samples): {dict(votes)}")
        print(f"  → decision={consensus.decision.role.value}  agreement={consensus.agreement:.2f}  "
              f"fell_back={consensus.fell_back}")
        if consensus.fell_back:
            print("  → samples disagreed below threshold → fell back to DETERMINISTIC classify_request "
                  "(deterministic backstop wins, same philosophy as the reconciliation gate)")


# --- Part B: reconciliation gate on REAL LLM analysis -------------------------

def _detector_tls_expiry() -> DetectorOutput:
    """A concrete, firing incident: TLS certificate expiry on the ingress."""
    alarm = AlarmContext(
        alarm_name="orders-api-5xx-spike",
        alarm_arn="arn:aws:cloudwatch:...:alarm/orders-api-5xx-spike",
        state="ALARM",
        reason="HTTPCode_Target_5XX_Count > 50 for 3 datapoints",
        metric_name="HTTPCode_Target_5XX_Count",
        namespace="orders",
        dimensions={"service": "orders-api"},
    )
    return DetectorOutput(
        alarm=alarm,
        log_insights_results=[
            {"@message": "x509: certificate has expired or is not yet valid"},
            {"@message": "TLS handshake error from upstream: certificate expired"},
            {"@message": "ingress-nginx: SSL certificate for orders.example.com expired"},
        ],
        related_metrics={"tls_handshake_errors": 214.0, "ssl_cert_days_remaining": -2.0},
    )


def _llm_root_cause(system: str, user: str) -> str:
    return _chat(system, user, temperature=0.7, max_tokens=48)


def demo_reconciliation() -> None:
    print("\n" + "=" * 78)
    print("PART B — Tier 1 reconciliation gate on REAL LLM analysis")
    print("=" * 78)
    detector = _detector_tls_expiry()
    evidence_snippet = "; ".join(r["@message"] for r in detector.log_insights_results)

    # B1 — GROUNDED: the analyst LLM is given the real evidence.
    grounded_rc = _llm_root_cause(
        "You are an SRE. In ONE short sentence, state the root cause of the incident from the logs.",
        f"Alarm: {detector.alarm.reason}\nLogs:\n{evidence_snippet}\nRoot cause:",
    )
    grounded = AnalyzerOutput(detector=detector, root_cause=grounded_rc, severity=Severity.P1, confidence=0.9)
    r1 = reconcile(detector, grounded)
    gate1 = apply_gate(RemediationMode.AUTO, r1)
    print("\n[B1 grounded] LLM saw the evidence")
    print(f"  LLM root_cause: {grounded_rc!r}")
    print(f"  grounded={r1.grounded}  grounding_ratio={r1.grounding_ratio:.2f}  issues={r1.issues}")
    print(f"  gate: AUTO → {gate1.value}   (grounded → autonomous action allowed)")

    # B2 — HALLUCINATION: the analyst LLM only gets a vague symptom, no evidence.
    #       It guesses a plausible-but-ungrounded cause; the gate must catch it.
    halluc_rc = _llm_root_cause(
        "You are an SRE. The orders-api service is returning some 5xx errors. In ONE short "
        "sentence, guess the single most likely root cause. Do not ask for logs.",
        "Most likely root cause:",
    )
    halluc = AnalyzerOutput(detector=detector, root_cause=halluc_rc, severity=Severity.P1, confidence=0.9)
    r2 = reconcile(detector, halluc)
    gate2 = apply_gate(RemediationMode.AUTO, r2)
    print("\n[B2 hallucination] LLM guessed WITHOUT the evidence")
    print(f"  LLM root_cause: {halluc_rc!r}")
    print(f"  grounded={r2.grounded}  grounding_ratio={r2.grounding_ratio:.2f}  issues={r2.issues}")
    print(f"  gate: AUTO → {gate2.value}   "
          + ("(ungrounded → DOWNGRADED to human approval)" if gate2 == RemediationMode.APPROVE
             else "(unexpectedly grounded — rerun; LLM guess happened to overlap evidence)"))


if __name__ == "__main__":
    print(f"endpoint={ENDPOINT}  model={MODEL}")
    demo_self_consistency()
    demo_reconciliation()
    print("\n" + "=" * 78)
    print("DONE — all paths above executed the shipped orchestration/reconciliation code.")
    print("=" * 78)
