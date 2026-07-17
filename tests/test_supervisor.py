"""Supervisor routing and A2A delegation tests."""

from src.agents.ai.gateway.a2a_server import A2AServer
from src.agents.ai.supervisor import (
    MAX_DELEGATED_INSTRUCTION,
    AgentRole,
    Supervisor,
    classify_request,
    matching_skills,
    sanitize_instruction,
)


KAGENT_CARD = {
    "name": "Kubernetes Agent",
    "skills": [{"id": "cluster-diagnostics", "name": "Cluster Diagnostics", "tags": ["cluster", "diagnostics"]}],
}


def test_classifies_explicit_provisioning_request():
    assert classify_request("Provision a k3s cluster with Ansible").role is AgentRole.PROVISION


def test_classifies_diagnostics_to_kagent():
    assert classify_request("Investigate why the payments pods are failing").role is AgentRole.KAGENT


def test_defaults_delivery_request_to_deploy():
    assert classify_request("Deploy orders-api v1.8.0 to the local cluster").role is AgentRole.DEPLOY


def test_does_not_execute_when_specialist_endpoint_is_unconfigured():
    outcome = Supervisor().handle("Deploy orders-api")

    assert outcome.decision.role is AgentRole.DEPLOY
    assert outcome.delegated is False
    assert outcome.trace[-1]["status"] == "not_configured"


def test_delegates_over_a2a_with_role_metadata():
    sent: dict = {}

    def transport(endpoint: str, body: dict) -> dict:
        sent["endpoint"] = endpoint
        sent["body"] = body
        return {"task": {"id": "remote-task"}}

    supervisor = Supervisor(
        {AgentRole.KAGENT: "http://kagent-agent"}, transport=transport, card_fetcher=lambda _: KAGENT_CARD
    )
    outcome = supervisor.handle("Show pod status", context_id="ctx-1")

    assert outcome.delegated is True
    assert sent["endpoint"] == "http://kagent-agent"
    assert sent["body"]["message"]["metadata"]["supervisorRole"] == "kagent"
    assert sent["body"]["message"]["contextId"] == "ctx-1"
    assert sent["body"]["message"]["metadata"]["matchedSkills"] == ["cluster-diagnostics"]


def test_reads_specialist_endpoint_from_environment(monkeypatch):
    monkeypatch.setenv("PLATFORM_KAGENT_A2A_URL", "http://kagent-agent")
    supervisor = Supervisor.from_environment(
        transport=lambda endpoint, body: {"endpoint": endpoint}, card_fetcher=lambda _: KAGENT_CARD
    )

    outcome = supervisor.handle("Show pod status")

    assert outcome.delegated is True
    assert outcome.response == {"endpoint": "http://kagent-agent"}


def test_refuses_delegation_when_discovered_card_has_no_matching_skill():
    supervisor = Supervisor(
        {AgentRole.KAGENT: "http://kagent-agent"}, card_fetcher=lambda _: {"name": "Deploy Agent", "skills": []}
    )

    outcome = supervisor.handle("Investigate pod status")

    assert outcome.delegated is False
    assert outcome.trace[-1]["status"] == "capability_mismatch"


def test_matches_kagent_card_capabilities():
    assert matching_skills(KAGENT_CARD, AgentRole.KAGENT) == ["cluster-diagnostics"]


def test_rejects_deploy_only_card_for_kagent_role():
    """A deploy specialist's card (kubernetes-tagged) must not satisfy KAGENT."""
    deploy_card = {
        "name": "Platform Deployer Agent",
        "skills": [
            {"id": "deploy-aws", "name": "AWS Deployment", "tags": ["aws", "eks", "kubernetes", "deployment"]},
            {"id": "rollback-deployment", "name": "Rollback", "tags": ["rollback", "cluster"]},
        ],
    }
    assert matching_skills(deploy_card, AgentRole.KAGENT) == []
    # ...but the same card still serves the DEPLOY role.
    assert matching_skills(deploy_card, AgentRole.DEPLOY) == ["deploy-aws", "rollback-deployment"]


def test_rejects_diagnostic_only_card_for_provision_role():
    """A read-only diagnostic card mentioning "Kubernetes cluster" must not be
    accepted as an infrastructure provisioner (generic "cluster" over-match)."""
    diagnostic_card = {
        "name": "local_diagnostic_agent",
        "skills": [
            {
                "id": "cluster-diagnostics",
                "name": "Cluster Diagnostics",
                "description": "Diagnose and troubleshoot Kubernetes cluster and workload issues.",
                "tags": ["diagnostic", "troubleshoot"],
            }
        ],
    }
    assert matching_skills(diagnostic_card, AgentRole.PROVISION) == []
    # ...but the KAGENT role still accepts it.
    assert matching_skills(diagnostic_card, AgentRole.KAGENT) == ["cluster-diagnostics"]
    # ...and a genuine provisioner card still matches PROVISION.
    provision_card = {
        "name": "Provisioner",
        "skills": [
            {"id": "provision-k3s", "name": "k3s Provisioning", "tags": ["ansible", "infrastructure"]},
        ],
    }
    assert matching_skills(provision_card, AgentRole.PROVISION) == ["provision-k3s"]


def test_uses_discovered_jsonrpc_url_for_kagent():
    sent: dict = {}
    card = {**KAGENT_CARD, "preferredTransport": "JSONRPC", "url": "http://k8s-agent.kagent:8080"}

    def transport(endpoint: str, body: dict) -> dict:
        sent["endpoint"] = endpoint
        sent["body"] = body
        return {"jsonrpc": "2.0", "result": {"id": "task-1"}}

    outcome = Supervisor(
        {AgentRole.KAGENT: "http://configured-endpoint"}, transport=transport, card_fetcher=lambda _: card
    ).handle("Investigate pod status")

    assert outcome.delegated is True
    assert sent["endpoint"] == card["url"]
    assert sent["body"]["method"] == "message/send"


def test_jsonrpc_message_includes_required_message_id():
    # Regression: the spec-compliant a2a SDK (kagent's server) rejects a
    # message/send whose params.message omits messageId (JSON-RPC -32602).
    # Verified live against a real kagent A2A agent in Phase 2.
    sent: dict = {}
    card = {**KAGENT_CARD, "preferredTransport": "JSONRPC", "url": "http://k8s-agent.kagent:8080"}

    def transport(endpoint: str, body: dict) -> dict:
        sent["body"] = body
        return {"jsonrpc": "2.0", "result": {"id": "task-1"}}

    Supervisor(
        {AgentRole.KAGENT: "http://configured-endpoint"}, transport=transport, card_fetcher=lambda _: card
    ).handle("Investigate pod status")

    message = sent["body"]["params"]["message"]
    assert message.get("messageId"), "A2A Message.messageId is required by the spec"


def test_gateway_returns_supervisor_route_trace():
    server = A2AServer()

    result = server.send_message({"role": "ROLE_USER", "parts": [{"text": "Deploy orders-api"}]})

    artifact = result["task"]["artifacts"][0]
    assert "deploy" in artifact["parts"][0]["text"]
    assert artifact["parts"][1]["data"]["route"] == "deploy"


# --- A2A boundary hardening: untrusted-instruction sanitize/cap (⑧ subset) ----


def test_sanitize_instruction_passes_clean_input_unchanged():
    text = "Deploy orders-api to staging\nwith canary rollout"
    cleaned, notes = sanitize_instruction(text)
    assert cleaned == text and notes == []


def test_sanitize_instruction_strips_control_chars_but_keeps_tab_newline():
    text = "Deploy\x07 orders\x00-api\twith\nnewline"
    cleaned, notes = sanitize_instruction(text)
    assert "\x07" not in cleaned and "\x00" not in cleaned
    assert "\t" in cleaned and "\n" in cleaned  # tab/newline preserved
    assert "stripped_control_chars" in notes


def test_sanitize_instruction_caps_length_with_marker():
    text = "A" * (MAX_DELEGATED_INSTRUCTION + 500)
    cleaned, notes = sanitize_instruction(text)
    assert len(cleaned) <= MAX_DELEGATED_INSTRUCTION + len(" …[truncated]")
    assert cleaned.endswith("…[truncated]")
    assert "truncated" in notes


def test_delegation_forwards_sanitized_instruction_and_traces_it():
    sent: dict = {}

    def transport(endpoint: str, body: dict) -> dict:
        sent["body"] = body
        return {"task": {"id": "t"}}

    supervisor = Supervisor(
        {AgentRole.KAGENT: "http://kagent-agent"}, transport=transport, card_fetcher=lambda _: KAGENT_CARD
    )
    outcome = supervisor.handle("Show pod status\x07 now")

    assert outcome.delegated is True
    # The control char is stripped from what crosses the boundary...
    forwarded = sent["body"]["message"]["parts"][0]["text"]
    assert "\x07" not in forwarded and forwarded == "Show pod status now"
    # ...and the transform is recorded in the audit trace.
    assert any(step.get("kind") == "sanitize" and "stripped_control_chars" in step["applied"] for step in outcome.trace)


def test_delegation_omits_sanitize_trace_for_clean_instruction():
    sent: dict = {}

    def transport(endpoint: str, body: dict) -> dict:
        sent["body"] = body
        return {"task": {"id": "t"}}

    supervisor = Supervisor(
        {AgentRole.KAGENT: "http://kagent-agent"}, transport=transport, card_fetcher=lambda _: KAGENT_CARD
    )
    outcome = supervisor.handle("Show pod status")

    assert sent["body"]["message"]["parts"][0]["text"] == "Show pod status"
    assert not any(step.get("kind") == "sanitize" for step in outcome.trace)


def test_supervisor_never_executes_mutating_work_without_the_a2a_boundary():
    """Delegation-safety invariant (⑧-4 guard): a mutating provision/deploy request
    must go out over the A2A transport — never be executed in-process — and with no
    endpoint configured the supervisor refuses rather than silently acting."""
    calls: list[str] = []

    def transport(endpoint: str, body: dict) -> dict:
        calls.append(endpoint)
        return {"task": {"id": "t"}}

    deploy_card = {"name": "Deployer", "skills": [{"id": "deploy-aws", "tags": ["deploy", "delivery"]}]}

    # Configured: the ONLY side effect is the A2A transport call.
    configured = Supervisor(
        {AgentRole.DEPLOY: "http://deploy-agent"}, transport=transport, card_fetcher=lambda _: deploy_card
    )
    outcome = configured.handle("Deploy orders-api to prod")
    assert outcome.delegated is True and calls == ["http://deploy-agent"]

    # Unconfigured: no endpoint -> refuse, and the transport is never invoked
    # (no in-process execution fallback for a mutating role).
    calls.clear()
    unconfigured = Supervisor(transport=transport)
    refused = unconfigured.handle("Deploy orders-api to prod")
    assert refused.delegated is False and calls == []
    assert refused.trace[-1]["status"] == "not_configured"
