"""Real-library check (no stubs, no network): import msft_deployer and build the agent with an
unusable credential. Construction must not call Azure; a token request would raise."""
import importlib.metadata as md
import json

from src.agents.ai import msft_deployer


class NoTokenCredential:
    def get_token(self, *scopes, **kwargs):
        raise AssertionError("construction must not request a token")


agent = msft_deployer.create_msft_deployer_agent(
    endpoint="https://example.services.ai.azure.com/api/projects/check",
    deployment_name="gpt-5-4", credential=NoTokenCredential())
client = agent.client
tools = {t.name: str(getattr(t, "approval_mode", None)) for t in agent.default_options.get("tools", [])} \
    if hasattr(agent, "default_options") else {}
print(json.dumps({
    "versions": {p: md.version(p) for p in ("agent-framework", "agent-framework-core", "agent-framework-foundry",
                                            "azure-ai-projects", "azure-identity")},
    "agent_type": f"{type(agent).__module__}.{type(agent).__name__}",
    "agent_name": agent.name,
    "client_type": f"{type(client).__module__}.{type(client).__name__}",
    "client_model": getattr(client, "model", None),
    "tools": tools,
}, indent=1))
