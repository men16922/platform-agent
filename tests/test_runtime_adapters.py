import pytest

from src.agents.adapters.runtime import (
    RuntimeSpec,
    get_runtime_adapter,
    supported_runtime_providers,
)
from src.agents.adapters.runtime import aws as aws_mod
from src.agents.adapters.runtime import azure as azure_mod
from src.agents.adapters.runtime import gcp as gcp_mod


class FakeClient:
    """Records AgentCore control-plane calls and returns canned responses."""

    def __init__(self, runtimes=None, create_resp=None):
        self.calls = []
        self._runtimes = runtimes or []
        self._create_resp = create_resp or {
            "agentRuntimeId": "rt-123",
            "agentRuntimeArn": "arn:aws:bedrock-agentcore:us-east-1:1:runtime/rt-123",
            "status": "CREATING",
        }

    def list_agent_runtimes(self, **kw):
        self.calls.append(("list", kw))
        return {"agentRuntimes": self._runtimes}

    def create_agent_runtime(self, **kw):
        self.calls.append(("create", kw))
        return self._create_resp

    def delete_agent_runtime(self, **kw):
        self.calls.append(("delete", kw))
        return {"status": "DELETING"}


def _inject(monkeypatch, client):
    monkeypatch.setattr(aws_mod, "_client", lambda region: client)
    return client


def test_registry_resolves_all_providers():
    assert supported_runtime_providers() == ["aws", "gcp", "azure"]
    assert isinstance(get_runtime_adapter("aws"), aws_mod.AgentCoreRuntimeAdapter)
    assert isinstance(get_runtime_adapter("gcp"), gcp_mod.AgentEngineRuntimeAdapter)
    assert isinstance(get_runtime_adapter("azure"), azure_mod.FoundryRuntimeAdapter)


def test_unknown_provider_raises():
    with pytest.raises(ValueError):
        get_runtime_adapter("onprem")


def test_host_is_preflight_only_without_approval(monkeypatch):
    client = _inject(monkeypatch, FakeClient(runtimes=[{"agentRuntimeName": "existing", "agentRuntimeId": "rt-9"}]))
    result = get_runtime_adapter("aws").host_agent(RuntimeSpec(agent_name="demo"))
    assert result.success is True
    assert result.status == "PREFLIGHT"
    # read-only list, never create
    assert [c[0] for c in client.calls] == ["list"]
    assert "existing" in result.output


def test_host_creates_when_approved(monkeypatch):
    client = _inject(monkeypatch, FakeClient())
    spec = RuntimeSpec(
        agent_name="demo",
        approved=True,
        image_uri="1.dkr.ecr.us-east-1.amazonaws.com/deployer:arm64",
        role_arn="arn:aws:iam::1:role/agentcore-exec",
        description="strands deployer",
        env={"PROVIDER": "aws"},
    )
    result = get_runtime_adapter("aws").host_agent(spec)
    assert result.success is True
    assert result.runtime_id == "rt-123"
    assert result.status == "CREATING"
    kind, kw = client.calls[0]
    assert kind == "create"
    assert kw["agentRuntimeName"] == "demo"
    assert kw["agentRuntimeArtifact"] == {
        "containerConfiguration": {"containerUri": "1.dkr.ecr.us-east-1.amazonaws.com/deployer:arm64"}
    }
    assert kw["roleArn"] == "arn:aws:iam::1:role/agentcore-exec"
    assert kw["networkConfiguration"] == {"networkMode": "PUBLIC"}
    assert kw["description"] == "strands deployer"
    assert kw["environmentVariables"] == {"PROVIDER": "aws"}


def test_host_approved_requires_image_and_role(monkeypatch):
    client = _inject(monkeypatch, FakeClient())
    # missing image_uri
    r1 = get_runtime_adapter("aws").host_agent(RuntimeSpec(approved=True, role_arn="arn:aws:iam::1:role/x"))
    assert r1.success is False and "image_uri" in (r1.error or "")
    # missing role_arn
    r2 = get_runtime_adapter("aws").host_agent(RuntimeSpec(approved=True, image_uri="img:arm64"))
    assert r2.success is False and "role_arn" in (r2.error or "")
    # nothing was sent to the API
    assert client.calls == []


def test_teardown_requires_approval(monkeypatch):
    _inject(monkeypatch, FakeClient())
    result = get_runtime_adapter("aws").teardown_agent(RuntimeSpec(agent_name="demo"))
    assert result.success is False
    assert "approved=True" in (result.error or "")


def test_teardown_resolves_id_by_name(monkeypatch):
    client = _inject(monkeypatch, FakeClient(runtimes=[{"agentRuntimeName": "demo", "agentRuntimeId": "rt-77"}]))
    result = get_runtime_adapter("aws").teardown_agent(RuntimeSpec(agent_name="demo", approved=True))
    assert result.success is True
    assert result.runtime_id == "rt-77"
    assert ("delete", {"agentRuntimeId": "rt-77"}) in client.calls


def test_teardown_unknown_name_errors(monkeypatch):
    client = _inject(monkeypatch, FakeClient(runtimes=[]))
    result = get_runtime_adapter("aws").teardown_agent(RuntimeSpec(agent_name="ghost", approved=True))
    assert result.success is False
    assert "no runtime found" in (result.error or "")
    assert not any(c[0] == "delete" for c in client.calls)


def test_boto_error_is_reported(monkeypatch):
    class Boom(FakeClient):
        def list_agent_runtimes(self, **kw):
            raise RuntimeError("AccessDeniedException")

    _inject(monkeypatch, Boom())
    result = get_runtime_adapter("aws").host_agent(RuntimeSpec(agent_name="demo"))
    assert result.success is False
    assert "AccessDenied" in (result.error or "")


# --- GCP (Vertex AI Agent Engine) ---


class _Engine:
    def __init__(self, name):
        self.display_name = name
        self.resource_name = f"projects/p/locations/l/reasoningEngines/{name}"


class FakeEngines:
    """Stand-in for the vertexai.agent_engines module."""

    def __init__(self, engines=None):
        self.calls = []
        self._engines = engines or []

    def list(self):
        self.calls.append(("list", None))
        return list(self._engines)

    def create(self, **kw):
        self.calls.append(("create", kw))
        return _Engine(kw.get("display_name", "created"))

    def delete(self, resource, **kw):
        self.calls.append(("delete", resource))


def _inject_gcp(monkeypatch, engines, project="proj-1"):
    monkeypatch.setenv("GCP_PROJECT", project)
    monkeypatch.setattr(gcp_mod, "_init", lambda project, location, staging_bucket: None)
    monkeypatch.setattr(gcp_mod, "_agent_engines", lambda: engines)
    return engines


def test_gcp_preflight_only_without_approval(monkeypatch):
    engines = _inject_gcp(monkeypatch, FakeEngines([_Engine("existing")]))
    result = get_runtime_adapter("gcp").host_agent(RuntimeSpec(agent_name="demo"))
    assert result.success is True
    assert result.status == "PREFLIGHT"
    assert [c[0] for c in engines.calls] == ["list"]
    assert "existing" in result.output


def test_gcp_requires_project(monkeypatch):
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    result = get_runtime_adapter("gcp").host_agent(RuntimeSpec(agent_name="demo"))
    assert result.success is False
    assert "GCP_PROJECT" in (result.error or "")


def test_gcp_creates_when_approved(monkeypatch):
    engines = _inject_gcp(monkeypatch, FakeEngines())
    spec = RuntimeSpec(agent_name="demo", approved=True, extra={"agent_object": object(), "requirements": ["strands-agents"]})
    result = get_runtime_adapter("gcp").host_agent(spec)
    assert result.success is True
    assert result.status == "DEPLOYED"
    kind, kw = engines.calls[0]
    assert kind == "create"
    assert kw["display_name"] == "demo"
    assert kw["requirements"] == ["strands-agents"]


def test_gcp_approved_requires_agent_object(monkeypatch):
    engines = _inject_gcp(monkeypatch, FakeEngines())
    result = get_runtime_adapter("gcp").host_agent(RuntimeSpec(agent_name="demo", approved=True))
    assert result.success is False
    assert "agent_object" in (result.error or "")
    assert engines.calls == []


def test_gcp_teardown_requires_approval(monkeypatch):
    _inject_gcp(monkeypatch, FakeEngines())
    result = get_runtime_adapter("gcp").teardown_agent(RuntimeSpec(agent_name="demo"))
    assert result.success is False
    assert "approved=True" in (result.error or "")


def test_gcp_teardown_resolves_by_name(monkeypatch):
    engines = _inject_gcp(monkeypatch, FakeEngines([_Engine("demo")]))
    result = get_runtime_adapter("gcp").teardown_agent(RuntimeSpec(agent_name="demo", approved=True))
    assert result.success is True
    assert any(c[0] == "delete" for c in engines.calls)


# --- Azure (AI Foundry Agents) ---


class _Agent:
    def __init__(self, name, id_):
        self.name = name
        self.id = id_


class FakeAgents:
    def __init__(self, agents=None):
        self.calls = []
        self._agents = agents or []

    def list_agents(self):
        self.calls.append(("list", None))
        return list(self._agents)

    def create_agent(self, **kw):
        self.calls.append(("create", kw))
        return _Agent(kw.get("name"), "asst-123")

    def delete_agent(self, agent_id):
        self.calls.append(("delete", agent_id))


class FakeAzureClient:
    def __init__(self, agents=None):
        self.agents = FakeAgents(agents)


def _inject_azure(monkeypatch, client, endpoint="https://foundry.example/api/projects/p"):
    monkeypatch.setenv("AZURE_AI_PROJECT_ENDPOINT", endpoint)
    monkeypatch.setattr(azure_mod, "_client", lambda ep: client)
    return client


def test_azure_preflight_only_without_approval(monkeypatch):
    client = _inject_azure(monkeypatch, FakeAzureClient([_Agent("existing", "asst-9")]))
    result = get_runtime_adapter("azure").host_agent(RuntimeSpec(agent_name="demo"))
    assert result.success is True
    assert result.status == "PREFLIGHT"
    assert [c[0] for c in client.agents.calls] == ["list"]
    assert "existing" in result.output


def test_azure_requires_endpoint(monkeypatch):
    monkeypatch.delenv("AZURE_AI_PROJECT_ENDPOINT", raising=False)
    result = get_runtime_adapter("azure").host_agent(RuntimeSpec(agent_name="demo"))
    assert result.success is False
    assert "AZURE_AI_PROJECT_ENDPOINT" in (result.error or "")


def test_azure_creates_when_approved(monkeypatch):
    client = _inject_azure(monkeypatch, FakeAzureClient())
    spec = RuntimeSpec(agent_name="demo", approved=True, extra={"model": "gpt-4o", "instructions": "deploy things"})
    result = get_runtime_adapter("azure").host_agent(spec)
    assert result.success is True
    assert result.runtime_id == "asst-123"
    kind, kw = client.agents.calls[0]
    assert kind == "create"
    assert kw["model"] == "gpt-4o"
    assert kw["name"] == "demo"
    assert kw["instructions"] == "deploy things"


def test_azure_approved_requires_model(monkeypatch):
    client = _inject_azure(monkeypatch, FakeAzureClient())
    result = get_runtime_adapter("azure").host_agent(RuntimeSpec(agent_name="demo", approved=True))
    assert result.success is False
    assert "model" in (result.error or "")
    assert client.agents.calls == []


def test_azure_teardown_resolves_by_name(monkeypatch):
    client = _inject_azure(monkeypatch, FakeAzureClient([_Agent("demo", "asst-77")]))
    result = get_runtime_adapter("azure").teardown_agent(RuntimeSpec(agent_name="demo", approved=True))
    assert result.success is True
    assert result.runtime_id == "asst-77"
    assert ("delete", "asst-77") in client.agents.calls
