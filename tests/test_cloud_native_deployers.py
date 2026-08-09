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

    def test_default_model(self, monkeypatch):
        from src.agents.ai.adk_deployer import create_adk_deployer_agent

        # The mocked Agent just records calls
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
        _mock_adk_agents.Agent.reset_mock()
        create_adk_deployer_agent()
        call_kwargs = _mock_adk_agents.Agent.call_args[1]
        assert "gemini" in call_kwargs["model"]

    def test_the_docstring_names_the_default_the_code_actually_uses(self, monkeypatch):
        """The old assertion was `"gemini" in model`, which passes for any Gemini.

        So when the code default moved to 3.5 the docstring kept saying 2.5 and
        nothing failed — a reader configuring from the docstring would pin an older
        model. The model ID is load-bearing (capability, cost, and any "3.5 or
        newer" requirement), so the documented default and the real one are pinned
        to each other rather than both being pinned to the word "gemini".
        """
        import re

        from src.agents.ai.adk_deployer import create_adk_deployer_agent

        monkeypatch.delenv("GEMINI_MODEL", raising=False)
        _mock_adk_agents.Agent.reset_mock()
        create_adk_deployer_agent()
        actual = _mock_adk_agents.Agent.call_args[1]["model"]

        documented = re.findall(r"gemini-[\w.\-]+", create_adk_deployer_agent.__doc__ or "")
        assert documented, "the docstring stopped naming a default at all"
        assert documented[-1].rstrip(".") == actual, (
            f"docstring says {documented[-1]!r}, code uses {actual!r}"
        )

    def test_the_env_var_still_wins(self, monkeypatch):
        """The documented override must keep working, or the doc is wrong again."""
        from src.agents.ai.adk_deployer import create_adk_deployer_agent

        monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-pro")
        _mock_adk_agents.Agent.reset_mock()
        create_adk_deployer_agent()
        assert _mock_adk_agents.Agent.call_args[1]["model"] == "gemini-3.5-pro"

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

class _StubSupervisor:
    """Stands in for Supervisor so card tests never touch model configuration."""

    def handle(self, text, context_id=None):  # pragma: no cover - never called here
        raise AssertionError("card tests must not dispatch messages")


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
        assert "capabilities" in card
        assert "defaultInputModes" in card
        assert "defaultOutputModes" in card
        assert "skills" in card

    def test_card_file_carries_no_absolute_addresses(self, card):
        """
        The card's interface `url` is the address a *remote* agent dials to
        reach us — the one field nobody here consumes, which is why it sat
        pointing at `platform-agent.example.com` through a full live A2A round
        trip while every test stayed green. The old guard asserted the field
        was *present*, never where it pointed.

        Addresses now come from `A2A_PUBLIC_URL` at serve time. Assert the file
        has no absolute address to drift out of date, and no placeholder hosts
        anywhere: a wrong address is paid for by whoever tries to consume us.
        """
        assert "supportedInterfaces" not in card, (
            "serve-time only — a hardcoded URL here cannot stay true across "
            "environments and nothing in this repo would notice it going stale"
        )
        # Only URL-valued fields — "localhost" is a real word in the deploy-local
        # skill description, and a guard that fires on prose gets loosened until
        # it stops firing on anything.
        def urls(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key == "url" and isinstance(value, str):
                        yield value
                    else:
                        yield from urls(value)
            elif isinstance(node, list):
                for item in node:
                    yield from urls(item)

        for url in urls(card):
            for placeholder in ("example.com", "example.org", "your-org", "localhost", "TODO", "CHANGEME"):
                assert placeholder not in url, f"placeholder {placeholder!r} in card url {url!r}"

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

    def test_served_card_publishes_the_configured_address(self, monkeypatch):
        """The served card — not the file — is what a remote agent reads."""
        from src.agents.ai.gateway.a2a_server import A2AServer

        monkeypatch.setenv("A2A_PUBLIC_URL", "https://agent.internal.example/a2a/v1/")
        served = A2AServer(supervisor=_StubSupervisor()).agent_card  # type: ignore[arg-type]
        iface = served["supportedInterfaces"][0]
        assert iface["url"] == "https://agent.internal.example/a2a/v1", "trailing slash normalised"
        assert iface["protocolBinding"] == "HTTP+JSON"
        assert iface["protocolVersion"] == "1.0"

    def test_unset_address_omits_the_interface_rather_than_guessing(self, monkeypatch):
        """
        No address is an honest "ask the operator". A guessed one sends whoever
        reads the card somewhere — the failure lands on them, not on us, which
        is precisely why it went unnoticed for so long.
        """
        from src.agents.ai.gateway.a2a_server import A2AServer

        monkeypatch.delenv("A2A_PUBLIC_URL", raising=False)
        served = A2AServer(supervisor=_StubSupervisor()).agent_card  # type: ignore[arg-type]
        assert "supportedInterfaces" not in served
        assert served["skills"], "the rest of the card must still be usable"

    def test_security_scheme(self, card):
        assert "securitySchemes" in card
        assert "bearer" in card["securitySchemes"]
        scheme = card["securitySchemes"]["bearer"]
        assert "httpAuthSecurityScheme" in scheme


class TestA2aAdvertisedAuthMatchesEnforcement:
    """
    The card declared `securitySchemes: bearer/JWT` while the server never
    looked at an Authorization header. That is the stale-URL defect pointed the
    other way, and the worse direction of the two: a remote agent reads the
    card, dutifully attaches a token, and concludes it is talking to an
    authenticated endpoint. Advertise only what is enforced.
    """

    def test_card_omits_the_scheme_when_enforcement_is_off(self, monkeypatch):
        from src.agents.ai.gateway.a2a_server import A2AServer

        monkeypatch.delenv("A2A_BEARER_TOKEN", raising=False)
        card = A2AServer(supervisor=_StubSupervisor()).agent_card  # type: ignore[arg-type]
        assert "securitySchemes" not in card
        assert "securityRequirements" not in card

    def test_card_advertises_the_scheme_once_enforcement_is_on(self, monkeypatch):
        from src.agents.ai.gateway.a2a_server import A2AServer

        monkeypatch.setenv("A2A_BEARER_TOKEN", "s3cret")
        card = A2AServer(supervisor=_StubSupervisor()).agent_card  # type: ignore[arg-type]
        assert "bearer" in card["securitySchemes"]
        assert card["securityRequirements"] == [{"bearer": []}]

    def test_enforcement_off_accepts_anonymous(self, monkeypatch):
        """The live kagent round trip calls anonymously; it must keep working."""
        from src.agents.ai.gateway.a2a_server import check_bearer

        monkeypatch.delenv("A2A_BEARER_TOKEN", raising=False)
        assert check_bearer(None) is True

    def test_enforcement_on_rejects_missing_wrong_and_malformed(self, monkeypatch):
        from src.agents.ai.gateway.a2a_server import check_bearer

        monkeypatch.setenv("A2A_BEARER_TOKEN", "s3cret")
        assert check_bearer("Bearer s3cret") is True
        assert check_bearer(None) is False, "missing token must not pass"
        assert check_bearer("Bearer wrong") is False
        assert check_bearer("s3cret") is False, "scheme is part of the contract"
        assert check_bearer("Basic s3cret") is False
