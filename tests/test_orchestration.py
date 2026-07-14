"""Self-consistency routing and agents-as-tools orchestration tests."""

from src.agents.ai.gateway.a2a_server import A2AServer
from src.agents.ai.orchestration import (
    Orchestrator,
    OrchestratorOutcome,
    PlanStep,
    RouteConsensus,
    route_with_self_consistency,
    single_step_planner,
)
from src.agents.ai.supervisor import AgentRole, RouteDecision, Supervisor


PROVISION_CARD = {
    "name": "Provisioner",
    "skills": [{"id": "provision-k3s", "name": "k3s", "tags": ["ansible", "infrastructure"]}],
}
DEPLOY_CARD = {
    "name": "Deployer",
    "skills": [{"id": "deploy-aws", "name": "AWS Deploy", "tags": ["deploy", "delivery"]}],
}
KAGENT_CARD = {
    "name": "Kubernetes Agent",
    "skills": [{"id": "cluster-diagnostics", "name": "Diagnostics", "tags": ["diagnostic"]}],
}


def _sampler_from(roles):
    """A stub LLM classifier that yields the given roles across successive calls."""
    it = iter(roles)

    def sampler(_instruction: str) -> RouteDecision:
        role = next(it)
        return RouteDecision(role, f"stub:{role.value}")

    return sampler


# --- self-consistency router -------------------------------------------------


def test_majority_vote_selects_plurality_role():
    sampler = _sampler_from(
        [AgentRole.DEPLOY, AgentRole.DEPLOY, AgentRole.DEPLOY, AgentRole.KAGENT, AgentRole.PROVISION]
    )
    consensus = route_with_self_consistency("do a thing", sampler=sampler, samples=5)

    assert consensus.decision.role is AgentRole.DEPLOY
    assert consensus.agreement == 0.6
    assert consensus.votes == {"deploy": 3, "kagent": 1, "provision": 1}
    assert consensus.fell_back is False


def test_low_agreement_falls_back_to_deterministic_classifier():
    # 2-2-1 split → winning share 0.4 < 0.6 → distrust the samples, use the
    # deterministic classifier on the instruction text instead.
    sampler = _sampler_from(
        [AgentRole.DEPLOY, AgentRole.KAGENT, AgentRole.PROVISION, AgentRole.DEPLOY, AgentRole.KAGENT]
    )
    consensus = route_with_self_consistency(
        "Provision a k3s cluster with Ansible", sampler=sampler, samples=5
    )

    assert consensus.fell_back is True
    assert consensus.decision.role is AgentRole.PROVISION  # from classify_request
    assert consensus.agreement == 0.4


def test_default_sampler_is_unanimous_and_never_falls_back():
    # Regression guard for the non-breaking claim: the deterministic default
    # sampler agrees with itself every call → agreement 1.0, no fallback.
    consensus = route_with_self_consistency("Deploy orders-api v1.8.0")

    assert consensus.decision.role is AgentRole.DEPLOY
    assert consensus.agreement == 1.0
    assert consensus.fell_back is False
    assert consensus.votes == {"deploy": 5}


def test_consensus_trace_frame_shape():
    consensus = route_with_self_consistency("Investigate pod status")
    frame = consensus.trace_frame()

    assert frame["kind"] == "consensus"
    assert frame["role"] == "kagent"
    assert frame["fell_back"] is False
    assert frame["samples"] == 5


# --- orchestrator: single-step (behavior-preserving) -------------------------


def test_single_step_orchestration_matches_supervisor_delegation():
    sent: dict = {}

    def transport(endpoint: str, body: dict) -> dict:
        sent["endpoint"] = endpoint
        sent["body"] = body
        return {"task": {"id": "remote-task"}}

    supervisor = Supervisor(
        {AgentRole.KAGENT: "http://kagent-agent"},
        transport=transport,
        card_fetcher=lambda _: KAGENT_CARD,
    )
    outcome = Orchestrator(supervisor).handle("Investigate pod status", context_id="ctx-1")

    assert isinstance(outcome, OrchestratorOutcome)
    assert outcome.delegated is True
    assert outcome.decision.role is AgentRole.KAGENT
    assert outcome.consensus.agreement == 1.0
    assert outcome.consensus.fell_back is False
    # Delegation reused Supervisor.handle verbatim, including context threading.
    assert sent["endpoint"] == "http://kagent-agent"
    assert sent["body"]["message"]["contextId"] == "ctx-1"
    # Trace carries a consensus frame then a plan frame with one delegated step.
    kinds = [frame["kind"] for frame in outcome.trace]
    assert kinds == ["consensus", "plan"]
    plan = outcome.trace[1]["steps"]
    assert len(plan) == 1 and plan[0]["delegated"] is True


def test_single_step_planner_returns_primary_decision():
    primary = RouteDecision(AgentRole.DEPLOY, "reason")
    steps = single_step_planner("Deploy orders-api", primary)
    assert steps == [PlanStep(primary, "Deploy orders-api")]


# --- orchestrator: multi-step chaining ---------------------------------------


def _provision_then_deploy(_instruction, _primary):
    return [
        PlanStep(RouteDecision(AgentRole.PROVISION, "step1"), "provision a k3s cluster"),
        PlanStep(RouteDecision(AgentRole.DEPLOY, "step2"), "deploy orders-api"),
    ]


def _card_for(endpoint: str) -> dict:
    return {"http://provision": PROVISION_CARD, "http://deploy": DEPLOY_CARD}[endpoint]


def test_multi_step_plan_runs_in_order_and_threads_context():
    calls: list[tuple[str, str | None]] = []

    def transport(endpoint: str, body: dict) -> dict:
        calls.append((endpoint, body["message"].get("contextId")))
        return {"task": {"id": "ok"}}

    supervisor = Supervisor(
        {AgentRole.PROVISION: "http://provision", AgentRole.DEPLOY: "http://deploy"},
        transport=transport,
        card_fetcher=_card_for,
    )
    orchestrator = Orchestrator(supervisor, planner=_provision_then_deploy)
    outcome = orchestrator.handle("stand up the app", context_id="ctx-9")

    assert outcome.delegated is True
    assert len(outcome.steps) == 2
    # Ordered provision → deploy, both sharing the same A2A contextId.
    assert calls == [("http://provision", "ctx-9"), ("http://deploy", "ctx-9")]
    plan = outcome.trace[1]["steps"]
    assert [s["role"] for s in plan] == ["provision", "deploy"]


def test_multi_step_plan_short_circuits_on_failed_step():
    calls: list[str] = []

    def transport(endpoint: str, body: dict) -> dict:
        calls.append(endpoint)
        return {"task": {"id": "ok"}}

    # Provision endpoint is NOT configured → first step fails to delegate, so the
    # dependent deploy step must never run.
    supervisor = Supervisor(
        {AgentRole.DEPLOY: "http://deploy"},
        transport=transport,
        card_fetcher=_card_for,
    )
    orchestrator = Orchestrator(supervisor, planner=_provision_then_deploy)
    outcome = orchestrator.handle("stand up the app")

    assert outcome.delegated is False
    assert len(outcome.steps) == 1  # stopped after the failed provision step
    assert outcome.steps[0].delegated is False
    assert calls == []  # deploy transport never called


# --- gateway wiring (opt-in) --------------------------------------------------


def test_gateway_orchestrator_path_stashes_consensus_and_steps():
    server = A2AServer(orchestrator=Orchestrator(Supervisor()))

    result = server.send_message({"role": "ROLE_USER", "parts": [{"text": "Deploy orders-api"}]})

    data = result["task"]["artifacts"][0]["parts"][1]["data"]
    assert data["route"] == "deploy"
    assert data["consensus"]["agreement"] == 1.0
    assert data["consensus"]["fell_back"] is False
    assert data["steps"] == [{"role": "deploy", "delegated": False}]


def test_gateway_env_flag_enables_orchestration(monkeypatch):
    monkeypatch.setenv("SUPERVISOR_ORCHESTRATION", "true")
    server = A2AServer()

    result = server.send_message({"role": "ROLE_USER", "parts": [{"text": "Deploy orders-api"}]})

    data = result["task"]["artifacts"][0]["parts"][1]["data"]
    assert "consensus" in data


def test_gateway_default_path_omits_consensus():
    server = A2AServer()

    result = server.send_message({"role": "ROLE_USER", "parts": [{"text": "Deploy orders-api"}]})

    data = result["task"]["artifacts"][0]["parts"][1]["data"]
    assert "consensus" not in data
    assert data["route"] == "deploy"


def test_route_consensus_to_dict_is_json_friendly():
    consensus = RouteConsensus(
        decision=RouteDecision(AgentRole.DEPLOY, "why"),
        agreement=0.6666666,
        votes={"deploy": 2, "kagent": 1},
        samples=3,
        fell_back=False,
    )
    assert consensus.to_dict() == {
        "role": "deploy",
        "reason": "why",
        "agreement": 0.6667,
        "votes": {"deploy": 2, "kagent": 1},
        "samples": 3,
        "fell_back": False,
    }
