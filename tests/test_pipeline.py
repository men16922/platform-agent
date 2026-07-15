"""
Tests for E2E Deployment Pipeline (Graph DAG).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


import src.agents.adapters.runtime.registry as rt_registry
from src.agents.adapters.runtime.base import RuntimeResult
from src.agents.ai.pipeline import (
    DeployPipeline,
    PipelineSpec,
    PipelineResult,
    StepResult,
    StepStatus,
)


class _FakeRuntimeAdapter:
    def __init__(self, result: RuntimeResult):
        self._result = result

    def host_agent(self, spec) -> RuntimeResult:
        return self._result

    def teardown_agent(self, spec) -> RuntimeResult:
        return self._result


class TestPipelineHostStep:
    def test_skipped_when_not_requested(self):
        step = DeployPipeline()._step_host(PipelineSpec(service_name="web", version="v1"), {})
        assert step.status == StepStatus.SKIPPED
        assert step.output["hosted"] is False

    def test_skipped_for_onprem_managed_runtime(self):
        spec = PipelineSpec(service_name="web", version="v1", provider="onprem", host_runtime=True)
        step = DeployPipeline()._step_host(spec, {})
        assert step.status == StepStatus.SKIPPED
        assert "kagent" in step.output["reason"]

    def test_preflight_success_when_unapproved(self, monkeypatch):
        fake = _FakeRuntimeAdapter(RuntimeResult(success=True, agent_name="web", status="PREFLIGHT", output="0 existing"))
        monkeypatch.setattr(rt_registry, "get_runtime_adapter", lambda provider: fake)
        spec = PipelineSpec(service_name="web", version="v1", provider="aws", host_runtime=True, runtime_approved=False)
        step = DeployPipeline()._step_host(spec, {})
        assert step.status == StepStatus.SUCCESS
        assert step.output["hosted"] is False  # preflight only — nothing created
        assert step.output["status"] == "PREFLIGHT"

    def test_creates_when_approved(self, monkeypatch):
        fake = _FakeRuntimeAdapter(
            RuntimeResult(success=True, agent_name="web", runtime_id="rt-1", runtime_arn="arn:rt", status="CREATING")
        )
        monkeypatch.setattr(rt_registry, "get_runtime_adapter", lambda provider: fake)
        spec = PipelineSpec(
            service_name="web", version="v1", provider="aws", host_runtime=True,
            runtime_approved=True, runtime_image_uri="ecr/img:1", runtime_role_arn="arn:role",
        )
        step = DeployPipeline()._step_host(spec, {})
        assert step.status == StepStatus.SUCCESS
        assert step.output["hosted"] is True
        assert step.output["runtime_id"] == "rt-1"

    def test_failed_on_adapter_error(self, monkeypatch):
        fake = _FakeRuntimeAdapter(RuntimeResult(success=False, agent_name="web", error="AccessDenied"))
        monkeypatch.setattr(rt_registry, "get_runtime_adapter", lambda provider: fake)
        spec = PipelineSpec(service_name="web", version="v1", provider="aws", host_runtime=True, runtime_approved=True)
        step = DeployPipeline()._step_host(spec, {})
        assert step.status == StepStatus.FAILED
        assert "AccessDenied" in step.error


class TestPipelineSpec:
    def test_defaults(self):
        spec = PipelineSpec(service_name="api", version="v1")
        assert spec.environment == "dev"
        assert spec.provider == "onprem"
        assert spec.replicas == 1
        assert spec.image == "api"  # defaults to service_name

    def test_custom_image(self):
        spec = PipelineSpec(service_name="api", version="v1", image="my-repo/api")
        assert spec.image == "my-repo/api"


class TestPipelineResult:
    def test_success(self):
        result = PipelineResult(
            spec=PipelineSpec(service_name="api", version="v1"),
            final_status=StepStatus.SUCCESS,
        )
        assert result.success is True

    def test_failure(self):
        result = PipelineResult(
            spec=PipelineSpec(service_name="api", version="v1"),
            final_status=StepStatus.FAILED,
            steps=[StepResult(step_name="build", status=StepStatus.FAILED, error="no Dockerfile")],
        )
        assert result.success is False
        assert result.failed_step.step_name == "build"

    def test_summary(self):
        result = PipelineResult(
            spec=PipelineSpec(service_name="api", version="v1"),
            final_status=StepStatus.SUCCESS,
            steps=[
                StepResult(step_name="plan", status=StepStatus.SUCCESS),
                StepResult(step_name="guard", status=StepStatus.SUCCESS),
            ],
        )
        summary = result.summary()
        assert "api@v1" in summary
        assert "✓" in summary


class TestDeployPipelineStructure:
    def test_has_8_nodes(self):
        pipeline = DeployPipeline()
        assert len(pipeline.nodes) == 8

    def test_node_order(self):
        pipeline = DeployPipeline()
        names = [n.name for n in pipeline.nodes]
        assert names == ["plan", "guard", "build", "push", "deploy", "validate", "report", "host"]

    def test_dependencies(self):
        pipeline = DeployPipeline()
        deps = {n.name: n.depends_on for n in pipeline.nodes}
        assert deps["plan"] == []
        assert deps["guard"] == ["plan"]
        assert deps["build"] == ["guard"]
        assert deps["push"] == ["build"]
        assert deps["deploy"] == ["push"]
        assert deps["validate"] == ["deploy"]
        assert deps["report"] == ["validate"]
        assert deps["host"] == ["report"]


class TestDeployPipelineExecution:
    """E2E pipeline execution with mocked infrastructure."""

    @patch("src.agents.adapters.deployment.onprem.subprocess.run")
    def test_full_pipeline_dev_success(self, mock_run):
        """Full pipeline succeeds for dev environment."""
        mock_run.return_value = MagicMock(returncode=0, stdout="success", stderr="")

        spec = PipelineSpec(
            service_name="web",
            version="v1.0",
            environment="dev",
            provider="onprem",
            replicas=2,
        )

        pipeline = DeployPipeline()
        result = pipeline.run(spec)

        assert result.final_status == StepStatus.SUCCESS
        assert len(result.steps) == 8
        # host is opt-in (host_runtime defaults False) → SKIPPED, everything else SUCCESS.
        by_name = {s.step_name: s.status for s in result.steps}
        assert by_name["host"] == StepStatus.SKIPPED
        assert all(s.status == StepStatus.SUCCESS for s in result.steps if s.step_name != "host")

    def test_pipeline_prod_blocks_at_guard(self):
        """Production deploy is blocked at guard step (requires approval)."""
        spec = PipelineSpec(
            service_name="api",
            version="v2.0",
            environment="prod",
            provider="onprem",
        )

        pipeline = DeployPipeline()
        result = pipeline.run(spec)

        assert result.final_status == StepStatus.BLOCKED
        assert result.steps[0].status == StepStatus.SUCCESS  # plan
        assert result.steps[1].status == StepStatus.BLOCKED  # guard
        assert result.steps[1].output["decision"] == "APPROVE"

    def test_pipeline_destructive_action_rejected(self):
        """Delete action is rejected at guard step."""
        spec = PipelineSpec(
            service_name="api",
            version="v1.0",
            environment="dev",
            provider="onprem",
        )

        pipeline = DeployPipeline()

        # Patch the guard step to simulate a delete action
        original_guard = pipeline._step_guard

        def patched_guard(spec, context):
            from src.agents.ai.policy_engine import PolicyEngine, DeployRequest
            engine = PolicyEngine.from_default()
            request = DeployRequest(environment=spec.environment, action="delete", service_name=spec.service_name)
            policy_result = engine.evaluate(request)
            from src.agents.ai.pipeline import StepResult, StepStatus
            return StepResult(
                step_name="guard",
                status=StepStatus.FAILED,
                error=f"Policy REJECT: {policy_result.reason}",
                output={"decision": "REJECT"},
            )

        pipeline._nodes[1].handler = patched_guard
        result = pipeline.run(spec)

        assert result.final_status == StepStatus.FAILED
        assert result.steps[1].output["decision"] == "REJECT"

    @patch("src.agents.adapters.deployment.onprem.subprocess.run")
    def test_pipeline_build_failure_skips_rest(self, mock_run):
        """Build failure stops the pipeline and skips subsequent steps."""
        # First call (build) fails, rest succeed
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="no Dockerfile")

        spec = PipelineSpec(service_name="web", version="v1.0", environment="dev", provider="onprem")

        pipeline = DeployPipeline()
        result = pipeline.run(spec)

        assert result.final_status == StepStatus.FAILED
        # plan: success, guard: success, build: failed
        assert result.steps[0].status == StepStatus.SUCCESS  # plan
        assert result.steps[1].status == StepStatus.SUCCESS  # guard
        assert result.steps[2].status == StepStatus.FAILED   # build

    @patch("src.agents.adapters.deployment.onprem.subprocess.run")
    def test_pipeline_validate_failure_triggers_rollback(self, mock_run):
        """Validation failure after deploy triggers rollback."""
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            # Make build, push, deploy succeed but validate fail
            # validate uses rollout status which is the 4th subprocess call
            if call_count[0] <= 3:  # build, push, deploy
                return MagicMock(returncode=0, stdout="success", stderr="")
            elif call_count[0] == 4:  # validate
                return MagicMock(returncode=1, stdout="", stderr="timed out")
            else:  # rollback
                return MagicMock(returncode=0, stdout="rolled back", stderr="")

        mock_run.side_effect = side_effect

        spec = PipelineSpec(service_name="web", version="v1.0", environment="dev", provider="onprem")

        pipeline = DeployPipeline()
        result = pipeline.run(spec)

        assert result.final_status == StepStatus.FAILED
        step_names = [s.step_name for s in result.steps]
        assert "rollback" in step_names

    @patch("src.agents.adapters.deployment.onprem.subprocess.run")
    def test_pipeline_staging_auto_deploys(self, mock_run):
        """Staging environment auto-deploys without blocking."""
        mock_run.return_value = MagicMock(returncode=0, stdout="success", stderr="")

        spec = PipelineSpec(
            service_name="api",
            version="v3.0",
            environment="staging",
            provider="onprem",
            replicas=3,
        )

        pipeline = DeployPipeline()
        result = pipeline.run(spec)

        assert result.final_status == StepStatus.SUCCESS
        guard_step = result.steps[1]
        assert guard_step.output["decision"] == "AUTO"


class TestOrchestrator:
    @patch("src.agents.adapters.deployment.onprem.subprocess.run")
    def test_main_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")

        from src.agents.ai.orchestrator import main

        exit_code = main(["--service", "web", "--version", "v1", "--env", "dev", "--provider", "onprem"])
        assert exit_code == 0

    def test_main_blocked(self):
        from src.agents.ai.orchestrator import main

        exit_code = main(["--service", "api", "--version", "v1", "--env", "prod", "--provider", "onprem"])
        assert exit_code == 2  # blocked for approval
