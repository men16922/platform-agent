"""
Local deployment adapters — docker build + localhost:5001 registry + kubectl.

Designed for the on-prem kind cluster created by `make local-cluster`.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

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


def _run(cmd: list[str], timeout: int = 60) -> tuple[int, str, str]:
    """Run a subprocess command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", f"Command timed out after {timeout}s: {' '.join(cmd)}"
    except FileNotFoundError:
        return 1, "", f"Command not found: {cmd[0]}"


class LocalBuildAdapter(BuildAdapter):
    """Build container images using local Docker."""

    provider = "local"

    def build(self, spec: ServiceSpec, context_path: str = ".") -> BuildResult:
        image_tag = f"localhost:5001/{spec.image}:{spec.version}"
        cmd = ["docker", "build", "-t", image_tag, context_path]
        rc, stdout, stderr = _run(cmd, timeout=300)

        if rc == 0:
            return BuildResult(success=True, image_tag=image_tag, logs=stdout)
        return BuildResult(success=False, image_tag=image_tag, error=stderr, logs=stdout)


class LocalRegistryAdapter(RegistryAdapter):
    """Push images to the local kind registry (localhost:5001)."""

    provider = "local"
    _registry_host = "localhost:5001"

    def push(self, image: str, tag: str) -> PushResult:
        image_uri = self.image_uri(image, tag)
        cmd = ["docker", "push", image_uri]
        rc, stdout, stderr = _run(cmd, timeout=120)

        if rc == 0:
            return PushResult(success=True, image_uri=image_uri)
        return PushResult(success=False, image_uri=image_uri, error=stderr)

    def image_uri(self, name: str, tag: str) -> str:
        return f"{self._registry_host}/{name}:{tag}"


class LocalClusterAdapter(ClusterAdapter):
    """Deploy to the local kind cluster using kubectl."""

    provider = "local"

    def deploy(self, spec: ServiceSpec, image_uri: str) -> DeployResult:
        manifest = self._generate_manifest(spec, image_uri)
        cmd = ["kubectl", "apply", "-f", "-", "--namespace", spec.namespace]
        try:
            result = subprocess.run(
                cmd,
                input=json.dumps(manifest),
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            return DeployResult(status=DeployStatus.FAILED, error=str(exc))

        if result.returncode == 0:
            return DeployResult(
                status=DeployStatus.SUCCESS,
                deployment_id=f"{spec.namespace}/{spec.name}",
                namespace=spec.namespace,
                replicas_desired=spec.replicas,
                endpoint=f"http://localhost:80",
            )
        return DeployResult(status=DeployStatus.FAILED, error=result.stderr)

    def validate(self, spec: ServiceSpec) -> ValidationResult:
        cmd = [
            "kubectl", "rollout", "status",
            f"deployment/{spec.name}",
            "--namespace", spec.namespace,
            "--timeout=60s",
        ]
        rc, stdout, stderr = _run(cmd, timeout=90)

        if rc == 0:
            return ValidationResult(healthy=True, checks_passed=1, checks_total=1, details=[stdout.strip()])
        return ValidationResult(healthy=False, checks_passed=0, checks_total=1, error=stderr)

    def rollback(self, spec: ServiceSpec) -> RollbackResult:
        cmd = [
            "kubectl", "rollout", "undo",
            f"deployment/{spec.name}",
            "--namespace", spec.namespace,
        ]
        rc, stdout, stderr = _run(cmd, timeout=60)

        if rc == 0:
            return RollbackResult(success=True, rolled_back_to="previous")
        return RollbackResult(success=False, error=stderr)

    def status(self, spec: ServiceSpec) -> DeployResult:
        cmd = [
            "kubectl", "get", "deployment", spec.name,
            "--namespace", spec.namespace,
            "-o", "json",
        ]
        rc, stdout, stderr = _run(cmd, timeout=30)

        if rc != 0:
            return DeployResult(status=DeployStatus.FAILED, error=stderr)

        try:
            data = json.loads(stdout)
            status = data.get("status", {})
            ready = status.get("readyReplicas", 0)
            desired = status.get("replicas", 0)
            deploy_status = DeployStatus.SUCCESS if ready == desired else DeployStatus.PENDING
            return DeployResult(
                status=deploy_status,
                deployment_id=f"{spec.namespace}/{spec.name}",
                namespace=spec.namespace,
                replicas_ready=ready,
                replicas_desired=desired,
            )
        except (json.JSONDecodeError, KeyError) as exc:
            return DeployResult(status=DeployStatus.FAILED, error=str(exc))

    def _generate_manifest(self, spec: ServiceSpec, image_uri: str) -> dict[str, Any]:
        """Generate a Kubernetes Deployment + Service manifest."""
        return {
            "apiVersion": "v1",
            "kind": "List",
            "items": [
                {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "metadata": {"name": spec.name, "namespace": spec.namespace},
                    "spec": {
                        "replicas": spec.replicas,
                        "selector": {"matchLabels": {"app": spec.name}},
                        "template": {
                            "metadata": {"labels": {"app": spec.name}},
                            "spec": {
                                "containers": [
                                    {
                                        "name": spec.name,
                                        "image": image_uri,
                                        "ports": [{"containerPort": p} for p in spec.ports],
                                        "resources": {
                                            "requests": spec.resources,
                                            "limits": spec.resources,
                                        },
                                        "livenessProbe": {
                                            "httpGet": {"path": spec.health_path, "port": spec.ports[0]},
                                            "initialDelaySeconds": 5,
                                            "periodSeconds": 10,
                                        },
                                        **({"env": [{"name": k, "value": v} for k, v in spec.env.items()]} if spec.env else {}),
                                    }
                                ]
                            },
                        },
                    },
                },
                {
                    "apiVersion": "v1",
                    "kind": "Service",
                    "metadata": {"name": spec.name, "namespace": spec.namespace},
                    "spec": {
                        "selector": {"app": spec.name},
                        "ports": [{"port": p, "targetPort": p} for p in spec.ports],
                        "type": "ClusterIP",
                    },
                },
            ],
        }
