"""
Tests for Strands deployer agent and tools.

Tests tool functions directly (without calling a real LLM) and verifies
the agent construction and system prompt.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agents.ai.strands_deployer import DEPLOYER_SYSTEM_PROMPT, create_deployer_agent
from src.agents.ai.tools import ALL_DEPLOY_TOOLS
from src.agents.ai.tools.build import build_image
from src.agents.ai.tools.push import push_image
from src.agents.ai.tools.deploy import deploy_to_cluster
from src.agents.ai.tools.validate import validate_deployment
from src.agents.ai.tools.rollback import rollback_deployment


# --- System Prompt Tests ---

class TestDeployerSystemPrompt:
    def test_prompt_defines_workflow_sequence(self):
        assert "Build" in DEPLOYER_SYSTEM_PROMPT
        assert "Push" in DEPLOYER_SYSTEM_PROMPT
        assert "Deploy" in DEPLOYER_SYSTEM_PROMPT
        assert "Validate" in DEPLOYER_SYSTEM_PROMPT
        assert "Rollback" in DEPLOYER_SYSTEM_PROMPT

    def test_prompt_includes_providers(self):
        assert "onprem" in DEPLOYER_SYSTEM_PROMPT
        assert "aws" in DEPLOYER_SYSTEM_PROMPT
        assert "gcp" in DEPLOYER_SYSTEM_PROMPT
        assert "azure" in DEPLOYER_SYSTEM_PROMPT

    def test_prompt_has_safety_rules(self):
        assert "CANNOT delete" in DEPLOYER_SYSTEM_PROMPT
        assert "rollback" in DEPLOYER_SYSTEM_PROMPT.lower()


# --- Agent Construction Tests ---

class TestCreateDeployerAgent:
    @patch("src.agents.ai.strands_deployer.Agent")
    def test_creates_agent_with_tools(self, mock_agent_cls):
        agent = create_deployer_agent(provider="onprem")

        mock_agent_cls.assert_called_once()
        call_kwargs = mock_agent_cls.call_args[1]
        assert "system_prompt" in call_kwargs
        assert "tools" in call_kwargs
        assert call_kwargs["tools"] == ALL_DEPLOY_TOOLS
        assert "onprem" in call_kwargs["system_prompt"]

    @patch("src.agents.ai.strands_deployer.Agent")
    def test_provider_appears_in_system_prompt(self, mock_agent_cls):
        create_deployer_agent(provider="aws")

        call_kwargs = mock_agent_cls.call_args[1]
        assert "Current provider: aws" in call_kwargs["system_prompt"]

    @patch("src.agents.ai.strands_deployer.Agent")
    def test_custom_model(self, mock_agent_cls):
        create_deployer_agent(provider="gcp", model="anthropic.claude-sonnet-4-20250514-v1:0")

        call_kwargs = mock_agent_cls.call_args[1]
        assert call_kwargs["model"] == "anthropic.claude-sonnet-4-20250514-v1:0"

    @patch("src.agents.ai.strands_deployer.Agent")
    def test_no_model_by_default(self, mock_agent_cls):
        create_deployer_agent(provider="onprem")

        call_kwargs = mock_agent_cls.call_args[1]
        assert "model" not in call_kwargs


# --- Tool Function Tests (direct invocation, mocking subprocess) ---

class TestBuildImageTool:
    @patch("src.agents.adapters.deployment.onprem.subprocess.run")
    def test_build_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="Built OK", stderr="")

        result = build_image.__wrapped__(
            service_name="api",
            image="api",
            version="v1",
            provider="onprem",
            context_path="/app",
        )

        assert result["success"] is True
        assert result["image_tag"] == "localhost:5001/api:v1"
        assert result["error"] == ""

    @patch("src.agents.adapters.deployment.onprem.subprocess.run")
    def test_build_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="no Dockerfile")

        result = build_image.__wrapped__(
            service_name="api", image="api", version="v1", provider="onprem"
        )

        assert result["success"] is False
        assert "no Dockerfile" in result["error"]


class TestPushImageTool:
    @patch("src.agents.adapters.deployment.onprem.subprocess.run")
    def test_push_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="Pushed", stderr="")

        result = push_image.__wrapped__(image="api", version="v1", provider="onprem")

        assert result["success"] is True
        assert result["image_uri"] == "localhost:5001/api:v1"

    @patch("src.agents.adapters.deployment.onprem.subprocess.run")
    def test_push_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="refused")

        result = push_image.__wrapped__(image="api", version="v1", provider="onprem")

        assert result["success"] is False


class TestDeployToClusterTool:
    @patch("src.agents.adapters.deployment.onprem.subprocess.run")
    def test_deploy_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="created", stderr="")

        result = deploy_to_cluster.__wrapped__(
            service_name="web",
            image="web",
            version="v1",
            image_uri="localhost:5001/web:v1",
            provider="onprem",
            replicas=2,
        )

        assert result["status"] == "success"
        assert result["deployment_id"] == "default/web"
        assert result["replicas_desired"] == 2

    @patch("src.agents.adapters.deployment.onprem.subprocess.run")
    def test_deploy_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="forbidden")

        result = deploy_to_cluster.__wrapped__(
            service_name="web",
            image="web",
            version="v1",
            image_uri="localhost:5001/web:v1",
            provider="onprem",
        )

        assert result["status"] == "failed"


class TestValidateDeploymentTool:
    @patch("src.agents.adapters.deployment.onprem.subprocess.run")
    def test_validate_healthy(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="successfully rolled out", stderr="")

        result = validate_deployment.__wrapped__(service_name="web", provider="onprem")

        assert result["healthy"] is True
        assert result["checks_passed"] == 1

    @patch("src.agents.adapters.deployment.onprem.subprocess.run")
    def test_validate_unhealthy(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="timed out")

        result = validate_deployment.__wrapped__(service_name="web", provider="onprem")

        assert result["healthy"] is False


class TestRollbackDeploymentTool:
    @patch("src.agents.adapters.deployment.onprem.subprocess.run")
    def test_rollback_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="rolled back", stderr="")

        result = rollback_deployment.__wrapped__(service_name="web", provider="onprem")

        assert result["success"] is True
        assert result["rolled_back_to"] == "previous"

    @patch("src.agents.adapters.deployment.onprem.subprocess.run")
    def test_rollback_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="not found")

        result = rollback_deployment.__wrapped__(service_name="web", provider="onprem")

        assert result["success"] is False


# --- Tool Registration Tests ---

class TestToolRegistration:
    def test_all_tools_are_callable(self):
        assert len(ALL_DEPLOY_TOOLS) == 5
        for t in ALL_DEPLOY_TOOLS:
            assert callable(t)

    def test_tools_have_names(self):
        names = {t.tool_name for t in ALL_DEPLOY_TOOLS}
        assert "build_image" in names
        assert "push_image" in names
        assert "deploy_to_cluster" in names
        assert "validate_deployment" in names
        assert "rollback_deployment" in names
