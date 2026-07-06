"""
Tests for cloud-native deployer agents (GCP ADK + Azure MS Agent Framework).

Tests tool functions directly (without calling a real LLM) and verifies
agent construction and system prompts.
"""

from __future__ import annotations

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest


# --- Mock external packages that may not be installed ---

# Mock google.adk
_mock_adk = MagicMock()
_mock_adk_agents = MagicMock()
_mock_adk.agents = _mock_adk_agents
sys.modules.setdefault("google.adk", _mock_adk)
sys.modules.setdefault("google.adk.agents", _mock_adk_agents)
sys.modules.setdefault("google.adk.agents.llm_agent", _mock_adk_agents)

# Mock agent_framework
_mock_af = MagicMock()
_mock_af.tool = MagicMock(side_effect=lambda **kwargs: lambda fn: fn)
_mock_af_azure = MagicMock()
sys.modules.setdefault("agent_framework", _mock_af)
sys.modules.setdefault("agent_framework.azure", _mock_af_azure)

# Mock azure.identity
_mock_azure_identity = MagicMock()
sys.modules.setdefault("azure", MagicMock())
sys.modules.setdefault("azure.identity", _mock_azure_identity)


# --- GCP Tool Tests ---

class TestGcpBuildImage:
    @patch("src.agents.adapters.deployment.gcp._run")
    def test_build_success(self, mock_run):
        mock_run.return_value = (0, "Built OK", "")

        from src.agents.ai.tools.gcp_build import gcp_build_image

        result = gcp_build_image(
            service_name="api",
            image="api",
            version="v1",
            context_path="/app",
        )

        assert result["success"] is True
        assert "api" in result["image_tag"]
        assert "v1" in result["image_tag"]
        assert result["error"] == ""

    @patch("src.agents.adapters.deployment.gcp._run")
    def test_build_failure(self, mock_run):
        mock_run.return_value = (1, "", "permission denied")

        from src.agents.ai.tools.gcp_build import gcp_build_image

        result = gcp_build_image(service_name="api", image="api", version="v1")

        assert result["success"] is False
        assert "permission denied" in result["error"]


class TestGcpPushImage:
    @patch("src.agents.adapters.deployment.gcp._run")
    def test_push_success(self, mock_run):
        mock_run.return_value = (0, "Pushed", "")

        from src.agents.ai.tools.gcp_push import gcp_push_image

        result = gcp_push_image(image="api", version="v1")

        assert result["success"] is True
        assert "api" in result["image_uri"]
        assert "v1" in result["image_uri"]

    @patch("src.agents.adapters.deployment.gcp._run")
    def test_push_failure(self, mock_run):
        mock_run.return_value = (1, "", "connection refused")

        from src.agents.ai.tools.gcp_push import gcp_push_image

        result = gcp_push_image(image="api", version="v1")

        assert result["success"] is False


class TestGcpDeployToCluster:
    @patch("src.agents.adapters.deployment.gcp.subprocess.run")
    def test_deploy_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="created", stderr="")

        from src.agents.ai.tools.gcp_deploy import gcp_deploy_to_cluster

        result = gcp_deploy_to_cluster(
            service_name="web",
            image="web",
            version="v1",
            image_uri="asia-northeast3-docker.pkg.dev/proj/web/web:v1",
            replicas=2,
        )

        assert result["status"] == "success"
        assert result["deployment_id"] == "default/web"
        assert result["replicas_desired"] == 2

    @patch("src.agents.adapters.deployment.gcp.subprocess.run")
    def test_deploy_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="forbidden")

        from src.agents.ai.tools.gcp_deploy import gcp_deploy_to_cluster

        result = gcp_deploy_to_cluster(
            service_name="web",
            image="web",
            version="v1",
            image_uri="asia-northeast3-docker.pkg.dev/proj/web/web:v1",
        )

        assert result["status"] == "failed"


class TestGcpValidateDeployment:
    @patch("src.agents.adapters.deployment.gcp._run")
    def test_validate_healthy(self, mock_run):
        mock_run.return_value = (0, "successfully rolled out", "")

        from src.agents.ai.tools.gcp_deploy import gcp_validate_deployment

        result = gcp_validate_deployment(service_name="web")

        assert result["healthy"] is True
        assert result["checks_passed"] == 1

    @patch("src.agents.adapters.deployment.gcp._run")
    def test_validate_unhealthy(self, mock_run):
        mock_run.return_value = (1, "", "timed out")

        from src.agents.ai.tools.gcp_deploy import gcp_validate_deployment

        result = gcp_validate_deployment(service_name="web")

        assert result["healthy"] is False


class TestGcpRollbackDeployment:
    @patch("src.agents.adapters.deployment.gcp._run")
    def test_rollback_success(self, mock_run):
        mock_run.return_value = (0, "rolled back", "")

        from src.agents.ai.tools.gcp_deploy import gcp_rollback_deployment

        result = gcp_rollback_deployment(service_name="web")

        assert result["success"] is True
        assert result["rolled_back_to"] == "previous"

    @patch("src.agents.adapters.deployment.gcp._run")
    def test_rollback_failure(self, mock_run):
        mock_run.return_value = (1, "", "not found")

        from src.agents.ai.tools.gcp_deploy import gcp_rollback_deployment

        result = gcp_rollback_deployment(service_name="web")

        assert result["success"] is False


# --- Azure Tool Tests ---

class TestAzureBuildImage:
    @patch("src.agents.adapters.deployment.azure._run")
    def test_build_success(self, mock_run):
        mock_run.return_value = (0, "Built OK", "")

        from src.agents.ai.tools.azure_build import azure_build_image

        result = azure_build_image(
            service_name="api",
            image="api",
            version="v1",
            context_path="/app",
        )

        assert result["success"] is True
        assert result["image_tag"] == "api:v1"
        assert result["error"] == ""

    @patch("src.agents.adapters.deployment.azure._run")
    def test_build_failure(self, mock_run):
        mock_run.return_value = (1, "", "registry not found")

        from src.agents.ai.tools.azure_build import azure_build_image

        result = azure_build_image(service_name="api", image="api", version="v1")

        assert result["success"] is False
        assert "registry not found" in result["error"]


class TestAzurePushImage:
    @patch("src.agents.adapters.deployment.azure._run")
    def test_push_success(self, mock_run):
        mock_run.return_value = (0, "Pushed", "")

        from src.agents.ai.tools.azure_push import azure_push_image

        result = azure_push_image(image="api", version="v1")

        assert result["success"] is True
        assert "azurecr.io" in result["image_uri"]

    @patch("src.agents.adapters.deployment.azure._run")
    def test_push_failure(self, mock_run):
        mock_run.return_value = (1, "", "auth failed")

        from src.agents.ai.tools.azure_push import azure_push_image

        result = azure_push_image(image="api", version="v1")

        assert result["success"] is False


class TestAzureDeployToCluster:
    @patch("src.agents.adapters.deployment.azure.subprocess.run")
    def test_deploy_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="created", stderr="")

        from src.agents.ai.tools.azure_deploy import azure_deploy_to_cluster

        result = azure_deploy_to_cluster(
            service_name="web",
            image="web",
            version="v1",
            image_uri="platformagentacr.azurecr.io/web:v1",
            replicas=3,
        )

        assert result["status"] == "success"
        assert result["deployment_id"] == "default/web"
        assert result["replicas_desired"] == 3

    @patch("src.agents.adapters.deployment.azure.subprocess.run")
    def test_deploy_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="quota exceeded")

        from src.agents.ai.tools.azure_deploy import azure_deploy_to_cluster

        result = azure_deploy_to_cluster(
            service_name="web",
            image="web",
            version="v1",
            image_uri="platformagentacr.azurecr.io/web:v1",
        )

        assert result["status"] == "failed"


class TestAzureValidateDeployment:
    @patch("src.agents.adapters.deployment.azure._run")
    def test_validate_healthy(self, mock_run):
        mock_run.return_value = (0, "successfully rolled out", "")

        from src.agents.ai.tools.azure_deploy import azure_validate_deployment

        result = azure_validate_deployment(service_name="web")

        assert result["healthy"] is True

    @patch("src.agents.adapters.deployment.azure._run")
    def test_validate_unhealthy(self, mock_run):
        mock_run.return_value = (1, "", "deadline exceeded")

        from src.agents.ai.tools.azure_deploy import azure_validate_deployment

        result = azure_validate_deployment(service_name="web")

        assert result["healthy"] is False


class TestAzureRollbackDeployment:
    @patch("src.agents.adapters.deployment.azure._run")
    def test_rollback_success(self, mock_run):
        mock_run.return_value = (0, "rolled back", "")

        from src.agents.ai.tools.azure_deploy import azure_rollback_deployment

        result = azure_rollback_deployment(service_name="web")

        assert result["success"] is True

    @patch("src.agents.adapters.deployment.azure._run")
    def test_rollback_failure(self, mock_run):
        mock_run.return_value = (1, "", "deployment not found")

        from src.agents.ai.tools.azure_deploy import azure_rollback_deployment

        result = azure_rollback_deployment(service_name="web")

        assert result["success"] is False


# --- ADK Deployer Agent Tests ---

class TestAdkDeployerAgent:
    def test_creates_agent_with_tools(self):
        from src.agents.ai.adk_deployer import create_adk_deployer_agent, GCP_DEPLOY_TOOLS

        agent = create_adk_deployer_agent()

        # AdkAgent is mocked at module level, so it returns a MagicMock
        # Verify tools are correct
        assert len(GCP_DEPLOY_TOOLS) == 5
        for t in GCP_DEPLOY_TOOLS:
            assert callable(t)

    def test_system_prompt_content(self):
        from src.agents.ai.adk_deployer import ADK_DEPLOYER_SYSTEM_PROMPT

        assert "GCP" in ADK_DEPLOYER_SYSTEM_PROMPT
        assert "GKE" in ADK_DEPLOYER_SYSTEM_PROMPT
        assert "Cloud Build" in ADK_DEPLOYER_SYSTEM_PROMPT
        assert "Artifact Registry" in ADK_DEPLOYER_SYSTEM_PROMPT
        assert "Build" in ADK_DEPLOYER_SYSTEM_PROMPT
        assert "Push" in ADK_DEPLOYER_SYSTEM_PROMPT
        assert "Deploy" in ADK_DEPLOYER_SYSTEM_PROMPT
        assert "Validate" in ADK_DEPLOYER_SYSTEM_PROMPT
        assert "Rollback" in ADK_DEPLOYER_SYSTEM_PROMPT
        assert "CANNOT delete" in ADK_DEPLOYER_SYSTEM_PROMPT

    def test_gcp_tools_are_functions(self):
        from src.agents.ai.adk_deployer import GCP_DEPLOY_TOOLS
        from src.agents.ai.tools.gcp_build import gcp_build_image
        from src.agents.ai.tools.gcp_push import gcp_push_image
        from src.agents.ai.tools.gcp_deploy import (
            gcp_deploy_to_cluster,
            gcp_validate_deployment,
            gcp_rollback_deployment,
        )

        assert gcp_build_image in GCP_DEPLOY_TOOLS
        assert gcp_push_image in GCP_DEPLOY_TOOLS
        assert gcp_deploy_to_cluster in GCP_DEPLOY_TOOLS
        assert gcp_validate_deployment in GCP_DEPLOY_TOOLS
        assert gcp_rollback_deployment in GCP_DEPLOY_TOOLS

    def test_default_model(self):
        from src.agents.ai.adk_deployer import create_adk_deployer_agent

        # The mocked Agent just records calls
        _mock_adk_agents.Agent.reset_mock()
        create_adk_deployer_agent()
        call_kwargs = _mock_adk_agents.Agent.call_args[1]
        assert "gemini" in call_kwargs["model"]

    def test_custom_model(self):
        from src.agents.ai.adk_deployer import create_adk_deployer_agent

        _mock_adk_agents.Agent.reset_mock()
        create_adk_deployer_agent(model="gemini-2.5-pro")
        call_kwargs = _mock_adk_agents.Agent.call_args[1]
        assert call_kwargs["model"] == "gemini-2.5-pro"


# --- MS Agent Framework Deployer Agent Tests ---

class TestMsftDeployerAgent:
    def test_system_prompt_content(self):
        from src.agents.ai.msft_deployer import MSFT_DEPLOYER_INSTRUCTIONS

        assert "Azure" in MSFT_DEPLOYER_INSTRUCTIONS
        assert "AKS" in MSFT_DEPLOYER_INSTRUCTIONS
        assert "ACR" in MSFT_DEPLOYER_INSTRUCTIONS
        assert "Build" in MSFT_DEPLOYER_INSTRUCTIONS
        assert "Push" in MSFT_DEPLOYER_INSTRUCTIONS
        assert "Deploy" in MSFT_DEPLOYER_INSTRUCTIONS
        assert "Validate" in MSFT_DEPLOYER_INSTRUCTIONS
        assert "Rollback" in MSFT_DEPLOYER_INSTRUCTIONS
        assert "CANNOT delete" in MSFT_DEPLOYER_INSTRUCTIONS

    def test_azure_tools_are_callable(self):
        from src.agents.ai.msft_deployer import AZURE_DEPLOY_TOOLS

        assert len(AZURE_DEPLOY_TOOLS) == 5
        for t in AZURE_DEPLOY_TOOLS:
            assert callable(t)

    def test_creates_agent(self):
        mock_client = MagicMock()
        mock_client.as_agent.return_value = MagicMock()
        _mock_af_azure.AzureOpenAIResponsesClient.return_value = mock_client

        from src.agents.ai.msft_deployer import create_msft_deployer_agent

        agent = create_msft_deployer_agent(
            endpoint="https://test.openai.azure.com",
            deployment_name="gpt-4o",
            credential=MagicMock(),
        )

        mock_client.as_agent.assert_called_once()
        call_kwargs = mock_client.as_agent.call_args[1]
        assert call_kwargs["name"] == "AzureDeployer"
        assert "tools" in call_kwargs


# --- A2A Agent Card Tests ---

class TestA2aAgentCard:
    @pytest.fixture
    def card(self):
        card_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "src",
            "agents",
            "ai",
            "a2a_card.json",
        )
        with open(card_path) as f:
            return json.load(f)

    def test_required_fields(self, card):
        assert "name" in card
        assert "description" in card
        assert "version" in card
        assert "supportedInterfaces" in card
        assert "capabilities" in card
        assert "defaultInputModes" in card
        assert "defaultOutputModes" in card
        assert "skills" in card

    def test_has_six_skills(self, card):
        assert len(card["skills"]) == 6

    def test_skill_ids(self, card):
        skill_ids = {s["id"] for s in card["skills"]}
        assert "deploy-aws" in skill_ids
        assert "deploy-gcp" in skill_ids
        assert "deploy-azure" in skill_ids
        assert "deploy-local" in skill_ids
        assert "validate-deployment" in skill_ids
        assert "rollback-deployment" in skill_ids

    def test_skills_have_required_fields(self, card):
        for skill in card["skills"]:
            assert "id" in skill
            assert "name" in skill
            assert "description" in skill
            assert "tags" in skill

    def test_supported_interfaces(self, card):
        interfaces = card["supportedInterfaces"]
        assert len(interfaces) >= 1
        iface = interfaces[0]
        assert "url" in iface
        assert "protocolBinding" in iface
        assert "protocolVersion" in iface
        assert iface["protocolVersion"] == "1.0"

    def test_security_scheme(self, card):
        assert "securitySchemes" in card
        assert "bearer" in card["securitySchemes"]
        scheme = card["securitySchemes"]["bearer"]
        assert "httpAuthSecurityScheme" in scheme
