"""
Tests for deployment adapters — factory, dataclasses, and provider implementations.
"""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock
import subprocess

import pytest

from src.agents.adapters.deployment.base import (
    BuildAdapter,
    BuildResult,
    ClusterAdapter,
    DeploymentAdapters,
    DeployResult,
    DeployStatus,
    PushResult,
    RegistryAdapter,
    RollbackResult,
    ServiceSpec,
    ValidationResult,
)
from src.agents.adapters.deployment.registry import (
    get_deployment_adapters,
    supported_deployment_providers,
)
from src.agents.adapters.deployment.local import (
    LocalBuildAdapter,
    LocalClusterAdapter,
    LocalRegistryAdapter,
)


# --- ServiceSpec ---

class TestServiceSpec:
    def test_defaults(self):
        spec = ServiceSpec(name="api", image="api", version="v1")
        assert spec.replicas == 1
        assert spec.ports == [8080]
        assert spec.health_path == "/healthz"
        assert spec.namespace == "default"
        assert spec.provider == "local"
        assert spec.resources == {"cpu": "250m", "memory": "256Mi"}

    def test_custom_values(self):
        spec = ServiceSpec(
            name="orders",
            image="orders-api",
            version="v2.1.0",
            replicas=3,
            ports=[8080, 9090],
            namespace="staging",
            provider="aws",
            env={"DB_HOST": "rds.internal"},
        )
        assert spec.replicas == 3
        assert spec.provider == "aws"
        assert spec.env["DB_HOST"] == "rds.internal"


# --- Factory ---

class TestDeploymentFactory:
    def test_supported_providers(self):
        providers = supported_deployment_providers()
        assert "local" in providers
        assert "aws" in providers
        assert "gcp" in providers
        assert "azure" in providers
        assert len(providers) == 4

    def test_get_local_adapters(self):
        adapters = get_deployment_adapters("local")
        assert isinstance(adapters, DeploymentAdapters)
        assert adapters.provider == "local"
        assert isinstance(adapters.build, BuildAdapter)
        assert isinstance(adapters.registry, RegistryAdapter)
        assert isinstance(adapters.cluster, ClusterAdapter)

    def test_get_aws_adapters(self):
        adapters = get_deployment_adapters("aws")
        assert adapters.provider == "aws"

    def test_get_gcp_adapters(self):
        adapters = get_deployment_adapters("gcp")
        assert adapters.provider == "gcp"

    def test_get_azure_adapters(self):
        adapters = get_deployment_adapters("azure")
        assert adapters.provider == "azure"

    def test_unsupported_provider_raises(self):
        with pytest.raises(ValueError, match="Unsupported deployment provider"):
            get_deployment_adapters("oracle")


# --- Local Build Adapter ---

class TestLocalBuildAdapter:
    def test_build_success(self):
        spec = ServiceSpec(name="app", image="app", version="v1")
        adapter = LocalBuildAdapter()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Successfully built abc123"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = adapter.build(spec, context_path="/tmp/src")

        assert result.success is True
        assert result.image_tag == "localhost:5001/app:v1"
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd == ["docker", "build", "-t", "localhost:5001/app:v1", "/tmp/src"]

    def test_build_failure(self):
        spec = ServiceSpec(name="app", image="app", version="v1")
        adapter = LocalBuildAdapter()

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Dockerfile not found"

        with patch("subprocess.run", return_value=mock_result):
            result = adapter.build(spec)

        assert result.success is False
        assert "Dockerfile not found" in result.error


# --- Local Registry Adapter ---

class TestLocalRegistryAdapter:
    def test_image_uri(self):
        adapter = LocalRegistryAdapter()
        uri = adapter.image_uri("myapp", "v2.0")
        assert uri == "localhost:5001/myapp:v2.0"

    def test_push_success(self):
        adapter = LocalRegistryAdapter()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Pushed"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = adapter.push("myapp", "v1")

        assert result.success is True
        assert result.image_uri == "localhost:5001/myapp:v1"

    def test_push_failure(self):
        adapter = LocalRegistryAdapter()

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "connection refused"

        with patch("subprocess.run", return_value=mock_result):
            result = adapter.push("myapp", "v1")

        assert result.success is False
        assert "connection refused" in result.error


# --- Local Cluster Adapter ---

class TestLocalClusterAdapter:
    def test_deploy_success(self):
        spec = ServiceSpec(name="web", image="web", version="v1", replicas=2)
        adapter = LocalClusterAdapter()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "deployment.apps/web created\nservice/web created"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = adapter.deploy(spec, "localhost:5001/web:v1")

        assert result.status == DeployStatus.SUCCESS
        assert result.deployment_id == "default/web"
        assert result.replicas_desired == 2
        call_kwargs = mock_run.call_args
        assert "--namespace" in call_kwargs[0][0] or any("--namespace" in str(a) for a in call_kwargs[0][0])

    def test_deploy_generates_valid_manifest(self):
        spec = ServiceSpec(name="api", image="api", version="v1", ports=[8080], replicas=3)
        adapter = LocalClusterAdapter()
        manifest = adapter._generate_manifest(spec, "localhost:5001/api:v1")

        assert manifest["apiVersion"] == "v1"
        assert manifest["kind"] == "List"
        assert len(manifest["items"]) == 2

        deployment = manifest["items"][0]
        assert deployment["kind"] == "Deployment"
        assert deployment["spec"]["replicas"] == 3
        container = deployment["spec"]["template"]["spec"]["containers"][0]
        assert container["image"] == "localhost:5001/api:v1"
        assert container["ports"][0]["containerPort"] == 8080
        assert "livenessProbe" in container

        service = manifest["items"][1]
        assert service["kind"] == "Service"
        assert service["spec"]["ports"][0]["port"] == 8080

    def test_validate_success(self):
        spec = ServiceSpec(name="api", image="api", version="v1")
        adapter = LocalClusterAdapter()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "deployment \"api\" successfully rolled out"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = adapter.validate(spec)

        assert result.healthy is True
        assert result.checks_passed == 1

    def test_rollback_success(self):
        spec = ServiceSpec(name="api", image="api", version="v1")
        adapter = LocalClusterAdapter()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "deployment.apps/api rolled back"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = adapter.rollback(spec)

        assert result.success is True
        assert result.rolled_back_to == "previous"


# --- AWS/GCP/Azure Registry Adapters (image_uri only, no real API calls) ---

class TestCloudRegistryUris:
    def test_aws_image_uri(self):
        from src.agents.adapters.deployment.aws import AwsRegistryAdapter
        adapter = AwsRegistryAdapter(account_id="123456789012", region="us-east-1")
        uri = adapter.image_uri("myapp", "v1")
        assert uri == "123456789012.dkr.ecr.us-east-1.amazonaws.com/myapp:v1"

    def test_gcp_image_uri(self):
        from src.agents.adapters.deployment.gcp import GcpRegistryAdapter
        with patch.dict("os.environ", {"GCP_PROJECT": "my-project", "GCP_REGION": "asia-northeast3"}):
            from importlib import reload
            import src.agents.adapters.deployment.gcp as gcp_mod
            reload(gcp_mod)
            adapter = gcp_mod.GcpRegistryAdapter()
            uri = adapter.image_uri("myapp", "v1")
            assert "docker.pkg.dev" in uri
            assert "myapp" in uri

    def test_azure_image_uri(self):
        from src.agents.adapters.deployment.azure import AzureRegistryAdapter
        with patch.dict("os.environ", {"AZURE_REGISTRY_NAME": "myacr"}):
            from importlib import reload
            import src.agents.adapters.deployment.azure as az_mod
            reload(az_mod)
            adapter = az_mod.AzureRegistryAdapter()
            uri = adapter.image_uri("myapp", "v1")
            assert uri == "myacr.azurecr.io/myapp:v1"


# --- DeployResult / DataClass tests ---

class TestDataclasses:
    def test_deploy_result_defaults(self):
        r = DeployResult()
        assert r.status == DeployStatus.PENDING
        assert r.replicas_ready == 0

    def test_build_result_success(self):
        r = BuildResult(success=True, image_tag="img:v1", build_id="b-123")
        assert r.success is True
        assert r.build_id == "b-123"

    def test_validation_result(self):
        r = ValidationResult(healthy=True, checks_passed=3, checks_total=3)
        assert r.healthy is True

    def test_rollback_result(self):
        r = RollbackResult(success=False, error="timeout")
        assert r.success is False
        assert r.error == "timeout"
