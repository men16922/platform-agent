"""
E2E Pipeline — Strands Graph DAG for autonomous deployment orchestration.

Orchestrates the full deployment lifecycle as a directed acyclic graph:
  Spec → Plan → Guard → Deploy → Validate → Report

Each node is a pipeline step that can succeed, fail, or require approval.

Usage:
    from src.agents.ai.pipeline import DeployPipeline, PipelineSpec

    spec = PipelineSpec(
        service_name="orders-api",
        version="v1.4.2",
        environment="staging",
        provider="onprem",
        replicas=2,
    )

    pipeline = DeployPipeline()
    result = pipeline.run(spec)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class StepStatus(str, Enum):
    """Status of a pipeline step."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"  # Waiting for approval


@dataclass
class PipelineSpec:
    """Input specification for the deployment pipeline."""

    service_name: str
    version: str
    environment: str = "dev"
    provider: str = "onprem"
    replicas: int = 1
    namespace: str = "default"
    image: str = ""
    context_path: str = "."
    health_path: str = "/healthz"

    def __post_init__(self):
        if not self.image:
            self.image = self.service_name


@dataclass
class StepResult:
    """Result of a single pipeline step."""

    step_name: str
    status: StepStatus
    output: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    duration_ms: int = 0


@dataclass
class PipelineResult:
    """Complete pipeline execution result."""

    spec: PipelineSpec
    steps: list[StepResult] = field(default_factory=list)
    final_status: StepStatus = StepStatus.PENDING

    @property
    def success(self) -> bool:
        return self.final_status == StepStatus.SUCCESS

    @property
    def failed_step(self) -> StepResult | None:
        for s in self.steps:
            if s.status == StepStatus.FAILED:
                return s
        return None

    def summary(self) -> str:
        lines = [f"Pipeline: {self.spec.service_name}@{self.spec.version} → {self.spec.environment}"]
        for s in self.steps:
            icon = {"success": "✓", "failed": "✗", "skipped": "⊘", "blocked": "⏸"}.get(s.status.value, "…")
            lines.append(f"  {icon} {s.step_name}: {s.status.value}")
        lines.append(f"  → Final: {self.final_status.value}")
        return "\n".join(lines)


class PipelineNode:
    """A node in the pipeline DAG."""

    def __init__(self, name: str, handler: Callable[[PipelineSpec, dict], StepResult], depends_on: list[str] | None = None):
        self.name = name
        self.handler = handler
        self.depends_on = depends_on or []


class DeployPipeline:
    """Directed Acyclic Graph pipeline for deployment orchestration.

    DAG structure:
        plan → guard → build → push → deploy → validate → report
                                                    ↓ (on failure)
                                                 rollback
    """

    def __init__(self):
        self._nodes: list[PipelineNode] = [
            PipelineNode("plan", self._step_plan),
            PipelineNode("guard", self._step_guard, depends_on=["plan"]),
            PipelineNode("build", self._step_build, depends_on=["guard"]),
            PipelineNode("push", self._step_push, depends_on=["build"]),
            PipelineNode("deploy", self._step_deploy, depends_on=["push"]),
            PipelineNode("validate", self._step_validate, depends_on=["deploy"]),
            PipelineNode("report", self._step_report, depends_on=["validate"]),
        ]

    @property
    def nodes(self) -> list[PipelineNode]:
        return self._nodes

    def run(self, spec: PipelineSpec) -> PipelineResult:
        """Execute the full pipeline DAG.

        Runs steps in topological order. If any step fails, subsequent
        steps are skipped and rollback is attempted.

        Args:
            spec: Pipeline input specification.

        Returns:
            PipelineResult with all step results.
        """
        result = PipelineResult(spec=spec)
        context: dict[str, Any] = {}  # Shared context between steps
        completed: set[str] = set()

        for node in self._nodes:
            # Check dependencies
            deps_met = all(d in completed for d in node.depends_on)
            if not deps_met:
                step_result = StepResult(step_name=node.name, status=StepStatus.SKIPPED, error="Dependencies not met")
                result.steps.append(step_result)
                continue

            # Execute the step
            step_result = node.handler(spec, context)
            result.steps.append(step_result)

            if step_result.status == StepStatus.SUCCESS:
                completed.add(node.name)
                context[node.name] = step_result.output
            elif step_result.status == StepStatus.BLOCKED:
                # Pipeline paused for approval
                result.final_status = StepStatus.BLOCKED
                return result
            else:
                # Step failed — attempt rollback if deploy was done
                if "deploy" in completed:
                    rollback_result = self._step_rollback(spec, context)
                    result.steps.append(rollback_result)
                result.final_status = StepStatus.FAILED
                return result

        result.final_status = StepStatus.SUCCESS
        return result

    # --- Pipeline Steps ---

    def _step_plan(self, spec: PipelineSpec, context: dict) -> StepResult:
        """Generate deployment plan from spec."""
        plan = {
            "service": spec.service_name,
            "version": spec.version,
            "environment": spec.environment,
            "provider": spec.provider,
            "replicas": spec.replicas,
            "namespace": spec.namespace,
            "image": f"{spec.image}:{spec.version}",
        }
        return StepResult(step_name="plan", status=StepStatus.SUCCESS, output=plan)

    def _step_guard(self, spec: PipelineSpec, context: dict) -> StepResult:
        """Evaluate policy rules (Guardian Agent)."""
        from src.agents.ai.policy_engine import PolicyEngine, DeployRequest

        engine = PolicyEngine.from_default()
        request = DeployRequest(
            environment=spec.environment,
            action="deploy",
            service_name=spec.service_name,
            replicas=spec.replicas,
            provider=spec.provider,
            namespace=spec.namespace,
        )
        policy_result = engine.evaluate(request)

        if policy_result.decision.value == "REJECT":
            return StepResult(
                step_name="guard",
                status=StepStatus.FAILED,
                error=f"Policy REJECT: {policy_result.reason}",
                output={"decision": "REJECT", "reason": policy_result.reason},
            )
        elif policy_result.decision.value == "APPROVE":
            return StepResult(
                step_name="guard",
                status=StepStatus.BLOCKED,
                output={"decision": "APPROVE", "reason": policy_result.reason},
            )

        return StepResult(
            step_name="guard",
            status=StepStatus.SUCCESS,
            output={"decision": "AUTO", "reason": policy_result.reason},
        )

    def _step_build(self, spec: PipelineSpec, context: dict) -> StepResult:
        """Build container image."""
        from src.agents.adapters.deployment import ServiceSpec, get_deployment_adapters

        adapters = get_deployment_adapters(spec.provider)
        svc_spec = ServiceSpec(name=spec.service_name, image=spec.image, version=spec.version, provider=spec.provider)
        result = adapters.build.build(svc_spec, context_path=spec.context_path)

        if result.success:
            return StepResult(step_name="build", status=StepStatus.SUCCESS, output={"image_tag": result.image_tag})
        return StepResult(step_name="build", status=StepStatus.FAILED, error=result.error)

    def _step_push(self, spec: PipelineSpec, context: dict) -> StepResult:
        """Push image to registry."""
        from src.agents.adapters.deployment import get_deployment_adapters

        adapters = get_deployment_adapters(spec.provider)
        result = adapters.registry.push(spec.image, spec.version)

        if result.success:
            return StepResult(step_name="push", status=StepStatus.SUCCESS, output={"image_uri": result.image_uri})
        return StepResult(step_name="push", status=StepStatus.FAILED, error=result.error)

    def _step_deploy(self, spec: PipelineSpec, context: dict) -> StepResult:
        """Deploy to cluster."""
        from src.agents.adapters.deployment import ServiceSpec, get_deployment_adapters

        adapters = get_deployment_adapters(spec.provider)
        image_uri = context.get("push", {}).get("image_uri", f"{spec.image}:{spec.version}")
        svc_spec = ServiceSpec(
            name=spec.service_name, image=spec.image, version=spec.version,
            provider=spec.provider, replicas=spec.replicas, namespace=spec.namespace,
            health_path=spec.health_path, ports=[8080],
        )
        result = adapters.cluster.deploy(svc_spec, image_uri)

        if result.status.value == "success":
            return StepResult(step_name="deploy", status=StepStatus.SUCCESS, output={"deployment_id": result.deployment_id})
        return StepResult(step_name="deploy", status=StepStatus.FAILED, error=result.error or "Deploy failed")

    def _step_validate(self, spec: PipelineSpec, context: dict) -> StepResult:
        """Validate deployment health."""
        from src.agents.adapters.deployment import ServiceSpec, get_deployment_adapters

        adapters = get_deployment_adapters(spec.provider)
        svc_spec = ServiceSpec(name=spec.service_name, image=spec.image, version="", provider=spec.provider, namespace=spec.namespace)
        result = adapters.cluster.validate(svc_spec)

        if result.healthy:
            return StepResult(step_name="validate", status=StepStatus.SUCCESS, output={"healthy": True})
        return StepResult(step_name="validate", status=StepStatus.FAILED, error=result.error or "Validation failed")

    def _step_report(self, spec: PipelineSpec, context: dict) -> StepResult:
        """Generate deployment report."""
        report = {
            "service": spec.service_name,
            "version": spec.version,
            "environment": spec.environment,
            "provider": spec.provider,
            "status": "deployed",
            "image_uri": context.get("push", {}).get("image_uri", ""),
            "deployment_id": context.get("deploy", {}).get("deployment_id", ""),
        }
        return StepResult(step_name="report", status=StepStatus.SUCCESS, output=report)

    def _step_rollback(self, spec: PipelineSpec, context: dict) -> StepResult:
        """Rollback on failure."""
        from src.agents.adapters.deployment import ServiceSpec, get_deployment_adapters

        adapters = get_deployment_adapters(spec.provider)
        svc_spec = ServiceSpec(name=spec.service_name, image=spec.image, version="", provider=spec.provider, namespace=spec.namespace)
        result = adapters.cluster.rollback(svc_spec)

        if result.success:
            return StepResult(step_name="rollback", status=StepStatus.SUCCESS, output={"rolled_back_to": result.rolled_back_to})
        return StepResult(step_name="rollback", status=StepStatus.FAILED, error=result.error or "Rollback failed")
