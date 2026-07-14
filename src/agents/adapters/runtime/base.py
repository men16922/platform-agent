"""Agent-runtime hosting adapters — cloud-neutral managed-runtime abstraction.

The ④ Host role: take a built agent (e.g. the Strands deployer) and stand it up
on a managed agent runtime. AWS = Bedrock AgentCore; later GCP = Vertex Agent
Engine, Azure = AI Foundry. Mirrors the provisioning adapters' plan-first /
apply-after-approval contract — hosting a runtime creates billable, hard-to-
reverse cloud infrastructure, so the mutating create runs only when approved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class RuntimeSpec:
    agent_name: str = "platform-agent-deployer"
    provider: str = "aws"
    region: str | None = None
    # ECR (ARM64) image implementing the runtime contract (/invocations, /ping).
    image_uri: str = ""
    # Execution role the managed runtime assumes.
    role_arn: str = ""
    network_mode: str = "PUBLIC"
    description: str = ""
    env: dict[str, str] = field(default_factory=dict)
    # Set on teardown when the caller already knows the runtime id; otherwise the
    # adapter resolves it by agent_name.
    runtime_id: str = ""
    approved: bool = False
    # Provider-specific create knobs the shared fields don't cover — e.g. GCP
    # {"staging_bucket","requirements","agent_object"}, Azure {"endpoint","model",
    # "instructions"}. Preflight + teardown use only the common fields.
    extra: dict = field(default_factory=dict)


@dataclass
class RuntimeResult:
    success: bool
    agent_name: str
    runtime_id: str | None = None
    runtime_arn: str | None = None
    status: str | None = None
    output: str = ""
    error: str | None = None


class RuntimeHostingAdapter(Protocol):
    def host_agent(self, spec: RuntimeSpec) -> RuntimeResult: ...

    def teardown_agent(self, spec: RuntimeSpec) -> RuntimeResult: ...
