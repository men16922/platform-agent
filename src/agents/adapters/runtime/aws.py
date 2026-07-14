"""AWS agent-runtime hosting adapter — Bedrock AgentCore, approval-gated.

Uses the boto3 ``bedrock-agentcore-control`` client (no extra dependency; the
AgentCore SDK / starter toolkit are not required for control-plane calls).
Mirrors the provisioning adapters' plan-first / apply-after-approval contract:

- unapproved ``host_agent`` runs a read-only preflight (``list_agent_runtimes``)
  — verifies auth + region and reports existing runtimes; creates nothing
- ``approved=True`` runs the real ``create_agent_runtime`` (needs an ECR image
  URI implementing the runtime contract + an execution role_arn)
- ``teardown_agent`` requires explicit approval and deletes by runtime id
  (resolved from the agent name when not supplied)

Requires: AWS credentials; ``AWS_REGION`` (or ``spec.region``) for the endpoint.
"""

from __future__ import annotations

import os

from src.agents.adapters.runtime.base import RuntimeResult, RuntimeSpec

_DEFAULT_REGION = "us-east-1"
_SERVICE = "bedrock-agentcore-control"


def _client(region: str):
    import boto3

    return boto3.client(_SERVICE, region_name=region)


def _region(spec: RuntimeSpec) -> str:
    return spec.region or os.getenv("AWS_REGION") or _DEFAULT_REGION


def _err(exc: Exception) -> str:
    # Keep boto3 error text compact for tool results / logs.
    return f"{type(exc).__name__}: {exc}"[:400]


class AgentCoreRuntimeAdapter:
    def host_agent(self, spec: RuntimeSpec) -> RuntimeResult:
        region = _region(spec)
        try:
            client = _client(region)
        except Exception as exc:  # missing creds / bad region
            return RuntimeResult(False, spec.agent_name, error=_err(exc))

        if not spec.approved:
            # Preflight: read-only. Verifies credentials + lists existing runtimes.
            try:
                resp = client.list_agent_runtimes(maxResults=20)
            except Exception as exc:
                return RuntimeResult(False, spec.agent_name, error=_err(exc))
            names = [r.get("agentRuntimeName") for r in resp.get("agentRuntimes", [])]
            return RuntimeResult(
                success=True,
                agent_name=spec.agent_name,
                status="PREFLIGHT",
                output=f"{len(names)} existing runtime(s): {names}",
            )

        # Mutating create — gated on approval + required artifact/role.
        if not spec.image_uri:
            return RuntimeResult(False, spec.agent_name, error="image_uri (ECR container) required to host")
        if not spec.role_arn:
            return RuntimeResult(False, spec.agent_name, error="role_arn (execution role) required to host")
        params: dict = {
            "agentRuntimeName": spec.agent_name,
            "agentRuntimeArtifact": {"containerConfiguration": {"containerUri": spec.image_uri}},
            "roleArn": spec.role_arn,
            "networkConfiguration": {"networkMode": spec.network_mode},
        }
        if spec.description:
            params["description"] = spec.description
        if spec.env:
            params["environmentVariables"] = spec.env
        try:
            resp = client.create_agent_runtime(**params)
        except Exception as exc:
            return RuntimeResult(False, spec.agent_name, error=_err(exc))
        return RuntimeResult(
            success=True,
            agent_name=spec.agent_name,
            runtime_id=resp.get("agentRuntimeId"),
            runtime_arn=resp.get("agentRuntimeArn"),
            status=resp.get("status", "CREATING"),
            output="agent runtime create requested",
        )

    def teardown_agent(self, spec: RuntimeSpec) -> RuntimeResult:
        if not spec.approved:
            return RuntimeResult(False, spec.agent_name, error="AgentCore teardown requires explicit approved=True")
        region = _region(spec)
        try:
            client = _client(region)
        except Exception as exc:
            return RuntimeResult(False, spec.agent_name, error=_err(exc))

        runtime_id = spec.runtime_id or self._resolve_id(client, spec.agent_name)
        if not runtime_id:
            return RuntimeResult(False, spec.agent_name, error=f"no runtime found for name '{spec.agent_name}'")
        try:
            client.delete_agent_runtime(agentRuntimeId=runtime_id)
        except Exception as exc:
            return RuntimeResult(False, spec.agent_name, runtime_id=runtime_id, error=_err(exc))
        return RuntimeResult(
            success=True,
            agent_name=spec.agent_name,
            runtime_id=runtime_id,
            status="DELETING",
            output="agent runtime delete requested",
        )

    def _resolve_id(self, client, agent_name: str) -> str:
        try:
            resp = client.list_agent_runtimes(maxResults=100)
        except Exception:
            return ""
        for r in resp.get("agentRuntimes", []):
            if r.get("agentRuntimeName") == agent_name:
                return r.get("agentRuntimeId", "")
        return ""
