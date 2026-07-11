"""Supervisor routing and A2A delegation tests."""

from src.agents.ai.gateway.a2a_server import A2AServer
from src.agents.ai.supervisor import AgentRole, Supervisor, classify_request, matching_skills


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


def test_gateway_returns_supervisor_route_trace():
    server = A2AServer()

    result = server.send_message({"role": "ROLE_USER", "parts": [{"text": "Deploy orders-api"}]})

    artifact = result["task"]["artifacts"][0]
    assert "deploy" in artifact["parts"][0]["text"]
    assert artifact["parts"][1]["data"]["route"] == "deploy"
