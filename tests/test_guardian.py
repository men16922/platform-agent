"""
Tests for Guardian Agent — policy engine and deployment gatekeeper.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.agents.ai.policy_engine import Decision, DeployRequest, PolicyEngine, PolicyResult


# --- PolicyEngine Tests ---

class TestPolicyEngineFromYaml:
    @pytest.fixture
    def engine(self):
        return PolicyEngine.from_default()

    def test_loads_rules(self, engine):
        assert len(engine._rules) == 7

    def test_rules_sorted_by_priority_desc(self, engine):
        priorities = [r.priority for r in engine._rules]
        assert priorities == sorted(priorities, reverse=True)

    def test_default_decision(self, engine):
        assert engine._default_decision == Decision.AUTO


class TestPolicyEngineEvaluation:
    @pytest.fixture
    def engine(self):
        return PolicyEngine.from_default()

    # --- Environment-based tests ---

    def test_prod_requires_approval(self, engine):
        request = DeployRequest(environment="prod", action="deploy")
        result = engine.evaluate(request)
        assert result.decision == Decision.APPROVE
        assert "prod-requires-approval" in result.matched_rules[0].id

    def test_production_requires_approval(self, engine):
        request = DeployRequest(environment="production", action="deploy")
        result = engine.evaluate(request)
        assert result.decision == Decision.APPROVE

    def test_staging_auto(self, engine):
        request = DeployRequest(environment="staging", action="deploy")
        result = engine.evaluate(request)
        assert result.decision == Decision.AUTO
        assert "staging-auto" in result.matched_rules[0].id

    def test_stg_auto(self, engine):
        request = DeployRequest(environment="stg", action="deploy")
        result = engine.evaluate(request)
        assert result.decision == Decision.AUTO

    def test_dev_auto(self, engine):
        request = DeployRequest(environment="dev", action="deploy")
        result = engine.evaluate(request)
        assert result.decision == Decision.AUTO

    def test_local_auto(self, engine):
        request = DeployRequest(environment="local", action="deploy")
        result = engine.evaluate(request)
        assert result.decision == Decision.AUTO

    # --- Destructive action tests (REJECT always wins) ---

    def test_delete_rejected(self, engine):
        request = DeployRequest(environment="dev", action="delete")
        result = engine.evaluate(request)
        assert result.decision == Decision.REJECT

    def test_terminate_rejected(self, engine):
        request = DeployRequest(environment="dev", action="terminate")
        result = engine.evaluate(request)
        assert result.decision == Decision.REJECT

    def test_drop_rejected(self, engine):
        request = DeployRequest(environment="dev", action="drop-database")
        result = engine.evaluate(request)
        assert result.decision == Decision.REJECT

    def test_destroy_rejected(self, engine):
        request = DeployRequest(environment="staging", action="destroy-cluster")
        result = engine.evaluate(request)
        assert result.decision == Decision.REJECT

    def test_delete_namespace_rejected(self, engine):
        request = DeployRequest(environment="dev", action="delete-namespace")
        result = engine.evaluate(request)
        assert result.decision == Decision.REJECT

    def test_reject_overrides_prod_approval(self, engine):
        """REJECT wins even for production (safety override)."""
        request = DeployRequest(environment="prod", action="delete-service")
        result = engine.evaluate(request)
        assert result.decision == Decision.REJECT

    # --- Scale-based tests ---

    def test_large_replicas_requires_approval(self, engine):
        request = DeployRequest(environment="staging", action="deploy", replicas=15)
        result = engine.evaluate(request)
        assert result.decision == Decision.APPROVE
        assert any("large-scale" in r.id for r in result.matched_rules)

    def test_normal_replicas_auto(self, engine):
        request = DeployRequest(environment="staging", action="deploy", replicas=3)
        result = engine.evaluate(request)
        assert result.decision == Decision.AUTO

    # --- Cross-region tests ---

    def test_cross_region_requires_approval(self, engine):
        request = DeployRequest(environment="staging", action="deploy", cross_region=True)
        result = engine.evaluate(request)
        assert result.decision == Decision.APPROVE
        assert any("cross-region" in r.id for r in result.matched_rules)

    # --- Default fallback ---

    def test_unknown_environment_uses_default(self, engine):
        request = DeployRequest(environment="unknown", action="deploy")
        result = engine.evaluate(request)
        assert result.decision == Decision.AUTO
        assert result.matched_rules == []
        assert "Default" in result.reason


class TestPolicyResult:
    def test_result_has_reason(self):
        result = PolicyResult(
            decision=Decision.AUTO,
            matched_rules=[],
            reason="Test reason",
        )
        assert result.reason == "Test reason"


class TestDeployRequest:
    def test_defaults(self):
        req = DeployRequest()
        assert req.environment == "dev"
        assert req.action == "deploy"
        assert req.replicas == 1
        assert req.cross_region is False

    def test_extra_fields(self):
        req = DeployRequest(extra={"custom_field": "value"})
        assert req.extra["custom_field"] == "value"


# --- Guardian Agent Tests ---

class TestGuardianAgent:
    @patch("src.agents.ai.guardian.Agent")
    def test_creates_agent_with_tools(self, mock_agent_cls):
        from src.agents.ai.guardian import create_guardian_agent, GUARDIAN_TOOLS

        create_guardian_agent()

        mock_agent_cls.assert_called_once()
        call_kwargs = mock_agent_cls.call_args[1]
        assert "system_prompt" in call_kwargs
        assert call_kwargs["tools"] == GUARDIAN_TOOLS

    @patch("src.agents.ai.guardian.Agent")
    def test_custom_model(self, mock_agent_cls):
        from src.agents.ai.guardian import create_guardian_agent

        create_guardian_agent(model="anthropic.claude-sonnet-4-20250514-v1:0")

        call_kwargs = mock_agent_cls.call_args[1]
        assert call_kwargs["model"] == "anthropic.claude-sonnet-4-20250514-v1:0"

    def test_system_prompt_content(self):
        from src.agents.ai.guardian import GUARDIAN_SYSTEM_PROMPT

        assert "Guardian" in GUARDIAN_SYSTEM_PROMPT
        assert "APPROVE" in GUARDIAN_SYSTEM_PROMPT
        assert "AUTO" in GUARDIAN_SYSTEM_PROMPT
        assert "REJECT" in GUARDIAN_SYSTEM_PROMPT
        assert "evaluate_policy" in GUARDIAN_SYSTEM_PROMPT


class TestGuardianToolDirect:
    """Test the @tool functions directly (unwrapped)."""

    def test_evaluate_policy_prod(self):
        from src.agents.ai.guardian import evaluate_policy

        result = evaluate_policy.__wrapped__(
            environment="prod",
            action="deploy",
            service_name="api",
            replicas=2,
        )

        assert result["decision"] == "APPROVE"
        assert len(result["matched_rules"]) > 0
        assert result["request"]["environment"] == "prod"

    def test_evaluate_policy_dev(self):
        from src.agents.ai.guardian import evaluate_policy

        result = evaluate_policy.__wrapped__(
            environment="dev",
            action="deploy",
        )

        assert result["decision"] == "AUTO"

    def test_evaluate_policy_delete(self):
        from src.agents.ai.guardian import evaluate_policy

        result = evaluate_policy.__wrapped__(
            environment="dev",
            action="delete",
        )

        assert result["decision"] == "REJECT"

    def test_list_policy_rules(self):
        from src.agents.ai.guardian import list_policy_rules

        result = list_policy_rules.__wrapped__()

        assert "rules" in result
        assert len(result["rules"]) == 7
        assert result["default_decision"] == "AUTO"


class TestEvaluateDeployRequest:
    """Test the direct programmatic API."""

    def test_direct_prod_approve(self):
        from src.agents.ai.guardian import evaluate_deploy_request

        result = evaluate_deploy_request(environment="prod", action="deploy")

        assert result.decision == Decision.APPROVE
        assert isinstance(result, PolicyResult)

    def test_direct_staging_auto(self):
        from src.agents.ai.guardian import evaluate_deploy_request

        result = evaluate_deploy_request(environment="staging")

        assert result.decision == Decision.AUTO

    def test_direct_delete_reject(self):
        from src.agents.ai.guardian import evaluate_deploy_request

        result = evaluate_deploy_request(action="delete")

        assert result.decision == Decision.REJECT
