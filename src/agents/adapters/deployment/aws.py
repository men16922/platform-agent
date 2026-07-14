"""
AWS deployment adapters — CodeBuild + ECR + EKS.

Requires: boto3, kubectl configured with EKS context.
"""

from __future__ import annotations

import json
import os
import subprocess

from src.agents.adapters.aws_session import assume_role_arn_from_env, assume_role_session
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


_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
_ACCOUNT_ID = os.getenv("AWS_ACCOUNT_ID", "")


def _run(cmd: list[str], timeout: int = 60) -> tuple[int, str, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return 1, "", str(exc)


class AwsBuildAdapter(BuildAdapter):
    """Build container images using AWS CodeBuild."""

    provider = "aws"

    def __init__(self, project_name: str = "platform-agent-build") -> None:
        self._project = project_name

    def build(self, spec: ServiceSpec, context_path: str = ".") -> BuildResult:
        try:
            # Honor an optional cross-account role (AWS_ASSUME_ROLE_ARN); unset →
            # in-account session, equivalent to boto3.client(...). boto3 absence
            # surfaces as ImportError from the lazy session build below.
            session = assume_role_session(assume_role_arn_from_env(), region=_REGION).session
            client = session.client("codebuild", region_name=_REGION)
        except ImportError:
            return BuildResult(success=False, error="boto3 not installed")
        try:
            response = client.start_build(
                projectName=self._project,
                environmentVariablesOverride=[
                    {"name": "IMAGE_NAME", "value": spec.image, "type": "PLAINTEXT"},
                    {"name": "IMAGE_TAG", "value": spec.version, "type": "PLAINTEXT"},
                ],
            )
            build_id = response["build"]["id"]
            return BuildResult(success=True, image_tag=f"{spec.image}:{spec.version}", build_id=build_id)
        except Exception as exc:
            return BuildResult(success=False, error=str(exc))


class AwsRegistryAdapter(RegistryAdapter):
    """Push images to Amazon ECR."""

    provider = "aws"

    def __init__(self, account_id: str = "", region: str = "") -> None:
        self._account = account_id or _ACCOUNT_ID
        self._region = region or _REGION

    def push(self, image: str, tag: str) -> PushResult:
        uri = self.image_uri(image, tag)
        cmd = ["docker", "push", uri]
        rc, stdout, stderr = _run(cmd, timeout=180)

        if rc == 0:
            return PushResult(success=True, image_uri=uri)
        return PushResult(success=False, image_uri=uri, error=stderr)

    def image_uri(self, name: str, tag: str) -> str:
        return f"{self._account}.dkr.ecr.{self._region}.amazonaws.com/{name}:{tag}"


class AwsClusterAdapter(ClusterAdapter):
    """Deploy to Amazon EKS using kubectl."""

    provider = "aws"

    def __init__(self, cluster_name: str = "platform-agent") -> None:
        self._cluster = cluster_name

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
