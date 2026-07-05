"""
Azure deployment adapters — ACR Tasks (build) + ACR (registry) + AKS (cluster).

Requires: az CLI configured, kubectl with AKS context.
"""

from __future__ import annotations

import json
import os
import subprocess

from src.agents.adapters.deployment.base import (
    BuildAdapter,
    BuildResult,
    ClusterAdapter,
    DeployResult,
    DeployStatus,
    PushResult,
    RegistryAdapter,
    RollbackResult,
    ServiceSpec,
    ValidationResult,
)


_RESOURCE_GROUP = os.getenv("AZURE_RESOURCE_GROUP", "platform-agent-rg")
_REGISTRY_NAME = os.getenv("AZURE_REGISTRY_NAME", "platformagentacr")
_REGION = os.getenv("AZURE_REGION", "koreacentral")


def _run(cmd: list[str], timeout: int = 60) -> tuple[int, str, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return 1, "", str(exc)


class AzureBuildAdapter(BuildAdapter):
    """Build container images using ACR Tasks (az acr build)."""

    provider = "azure"

    def build(self, spec: ServiceSpec, context_path: str = ".") -> BuildResult:
        image_tag = f"{spec.image}:{spec.version}"
        cmd = [
            "az", "acr", "build",
            "--registry", _REGISTRY_NAME,
            "--resource-group", _RESOURCE_GROUP,
            "--image", image_tag,
            context_path,
        ]
        rc, stdout, stderr = _run(cmd, timeout=600)

        if rc == 0:
            return BuildResult(success=True, image_tag=image_tag, logs=stdout)
        return BuildResult(success=False, image_tag=image_tag, error=stderr)


class AzureRegistryAdapter(RegistryAdapter):
    """Push images to Azure Container Registry."""

    provider = "azure"

    def push(self, image: str, tag: str) -> PushResult:
        uri = self.image_uri(image, tag)
        cmd = ["docker", "push", uri]
        rc, stdout, stderr = _run(cmd, timeout=180)

        if rc == 0:
            return PushResult(success=True, image_uri=uri)
        return PushResult(success=False, image_uri=uri, error=stderr)

    def image_uri(self, name: str, tag: str) -> str:
        return f"{_REGISTRY_NAME}.azurecr.io/{name}:{tag}"


class AzureClusterAdapter(ClusterAdapter):
    """Deploy to Azure Kubernetes Service using kubectl."""

    provider = "azure"

    def deploy(self, spec: ServiceSpec, image_uri: str) -> DeployResult:
        manifest = self._generate_manifest(spec, image_uri)
        cmd = ["kubectl", "apply", "-f", "-", "--namespace", spec.namespace]
        try:
            result = subprocess.run(
                cmd, input=json.dumps(manifest), capture_output=True, text=True, timeout=60
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            return DeployResult(status=DeployStatus.FAILED, error=str(exc))

        if result.returncode == 0:
            return DeployResult(
                status=DeployStatus.SUCCESS,
                deployment_id=f"{spec.namespace}/{spec.name}",
                namespace=spec.namespace,
                replicas_desired=spec.replicas,
            )
        return DeployResult(status=DeployStatus.FAILED, error=result.stderr)

    def validate(self, spec: ServiceSpec) -> ValidationResult:
        cmd = [
            "kubectl", "rollout", "status", f"deployment/{spec.name}",
            "--namespace", spec.namespace, "--timeout=120s",
        ]
        rc, stdout, stderr = _run(cmd, timeout=150)
        if rc == 0:
            return ValidationResult(healthy=True, checks_passed=1, checks_total=1, details=[stdout.strip()])
        return ValidationResult(healthy=False, checks_passed=0, checks_total=1, error=stderr)

    def rollback(self, spec: ServiceSpec) -> RollbackResult:
        cmd = ["kubectl", "rollout", "undo", f"deployment/{spec.name}", "--namespace", spec.namespace]
        rc, stdout, stderr = _run(cmd, timeout=60)
        if rc == 0:
            return RollbackResult(success=True, rolled_back_to="previous")
        return RollbackResult(success=False, error=stderr)

    def status(self, spec: ServiceSpec) -> DeployResult:
        cmd = ["kubectl", "get", "deployment", spec.name, "--namespace", spec.namespace, "-o", "json"]
        rc, stdout, stderr = _run(cmd, timeout=30)
        if rc != 0:
            return DeployResult(status=DeployStatus.FAILED, error=stderr)
        try:
            data = json.loads(stdout)
            ready = data.get("status", {}).get("readyReplicas", 0)
            desired = data.get("status", {}).get("replicas", 0)
            return DeployResult(
                status=DeployStatus.SUCCESS if ready == desired else DeployStatus.PENDING,
                deployment_id=f"{spec.namespace}/{spec.name}",
                namespace=spec.namespace,
                replicas_ready=ready,
                replicas_desired=desired,
            )
        except (json.JSONDecodeError, KeyError) as exc:
            return DeployResult(status=DeployStatus.FAILED, error=str(exc))

    def _generate_manifest(self, spec: ServiceSpec, image_uri: str) -> dict:
        from src.agents.adapters.deployment.local import LocalClusterAdapter
        return LocalClusterAdapter()._generate_manifest(spec, image_uri)
