"""GCP agent-runtime hosting adapter — Vertex AI Agent Engine, approval-gated.

Uses the ``vertexai`` SDK (``vertexai.agent_engines``). Mirrors the AWS adapter's
plan-first / apply-after-approval contract:

- unapproved ``host_agent`` runs a read-only preflight (``agent_engines.list``)
  — verifies auth + project/location and reports existing engines; creates nothing
- ``approved=True`` runs the real ``agent_engines.create`` (needs a deployable
  agent object in ``spec.extra['agent_object']`` + optional requirements)
- ``teardown_agent`` requires explicit approval and deletes by resource name
  (resolved from the agent name when not supplied)

Config from the same env as the deployment/provisioning adapters: ``GCP_PROJECT``
(required) and ``GCP_REGION`` (falls back to an Agent Engine region).
"""

from __future__ import annotations

import os

from src.agents.adapters.runtime.base import RuntimeResult, RuntimeSpec

_DEFAULT_LOCATION = "us-central1"


def _init(project: str, location: str, staging_bucket: str | None) -> None:
    import vertexai

    vertexai.init(project=project, location=location, staging_bucket=staging_bucket or None)


def _agent_engines():
    from vertexai import agent_engines

    return agent_engines


def _location(spec: RuntimeSpec) -> str:
    return spec.region or os.getenv("GCP_REGION", _DEFAULT_LOCATION)


def _err(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"[:400]


def _label(engine) -> str | None:
    return getattr(engine, "display_name", None) or getattr(engine, "name", None)


class AgentEngineRuntimeAdapter:
    def host_agent(self, spec: RuntimeSpec) -> RuntimeResult:
        project = os.getenv("GCP_PROJECT", "")
        if not project:
            return RuntimeResult(False, spec.agent_name, error="GCP_PROJECT not set")
        try:
            _init(project, _location(spec), spec.extra.get("staging_bucket"))
            engines = _agent_engines()
        except Exception as exc:
            return RuntimeResult(False, spec.agent_name, error=_err(exc))

        if not spec.approved:
            try:
                existing = list(engines.list())
            except Exception as exc:
                return RuntimeResult(False, spec.agent_name, error=_err(exc))
            names = [_label(e) for e in existing]
            return RuntimeResult(
                success=True,
                agent_name=spec.agent_name,
                status="PREFLIGHT",
                output=f"{len(names)} existing engine(s): {names}",
            )

        agent_object = spec.extra.get("agent_object")
        if agent_object is None:
            return RuntimeResult(False, spec.agent_name, error="extra['agent_object'] (deployable agent) required to host")
        try:
            created = engines.create(
                agent_engine=agent_object,
                display_name=spec.agent_name,
                requirements=spec.extra.get("requirements", []),
                description=spec.description or None,
            )
        except Exception as exc:
            return RuntimeResult(False, spec.agent_name, error=_err(exc))
        return RuntimeResult(
            success=True,
            agent_name=spec.agent_name,
            runtime_id=getattr(created, "resource_name", None) or getattr(created, "name", None),
            status="DEPLOYED",
            output="agent engine created",
        )

    def teardown_agent(self, spec: RuntimeSpec) -> RuntimeResult:
        if not spec.approved:
            return RuntimeResult(False, spec.agent_name, error="Agent Engine teardown requires explicit approved=True")
        project = os.getenv("GCP_PROJECT", "")
        if not project:
            return RuntimeResult(False, spec.agent_name, error="GCP_PROJECT not set")
        try:
            _init(project, _location(spec), spec.extra.get("staging_bucket"))
            engines = _agent_engines()
        except Exception as exc:
            return RuntimeResult(False, spec.agent_name, error=_err(exc))

        resource = spec.runtime_id or self._resolve(engines, spec.agent_name)
        if not resource:
            return RuntimeResult(False, spec.agent_name, error=f"no engine found for name '{spec.agent_name}'")
        try:
            engines.delete(resource, force=True)
        except Exception as exc:
            return RuntimeResult(False, spec.agent_name, runtime_id=resource, error=_err(exc))
        return RuntimeResult(
            success=True,
            agent_name=spec.agent_name,
            runtime_id=resource,
            status="DELETING",
            output="agent engine delete requested",
        )

    def _resolve(self, engines, agent_name: str) -> str:
        try:
            for e in engines.list():
                if _label(e) == agent_name:
                    return getattr(e, "resource_name", None) or getattr(e, "name", "") or ""
        except Exception:
            return ""
        return ""
