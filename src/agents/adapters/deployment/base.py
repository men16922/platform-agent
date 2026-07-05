"""
Deployment adapter abstractions for multi-cloud container deployment.

Each provider (local/aws/gcp/azure) implements these ABCs to support the
unified deployment workflow: Build → Push → Deploy → Validate → Rollback.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DeployStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    ROLLED_BACK = "rolled_back"


@dataclass
class ServiceSpec:
    """Cloud-neutral service deployment specification."""

    name: str
    image: str
    version: str
    replicas: int = 1
    ports: list[int] = field(default_factory=lambda: [8080])
    health_path: str = "/healthz"
    namespace: str = "default"
    provider: str = "local"
    resources: dict[str, str] = field(default_factory=lambda: {"cpu": "250m", "memory": "256Mi"})
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class BuildResult:
    """Result of an image build operation."""

    success: bool
    image_tag: str = ""
    build_id: str = ""
    logs: str = ""
    error: str = ""


@dataclass
class PushResult:
    """Result of an image push to registry."""

    success: bool
    image_uri: str = ""
    digest: str = ""
    error: str = ""


@dataclass
class DeployResult:
    """Result of a deployment to a cluster."""

    status: DeployStatus = DeployStatus.PENDING
    deployment_id: str = ""
    namespace: str = "default"
    replicas_ready: int = 0
    replicas_desired: int = 0
    endpoint: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Result of a post-deployment validation."""

    healthy: bool
    checks_passed: int = 0
    checks_total: int = 0
    response_time_ms: float = 0.0
    details: list[str] = field(default_factory=list)
    error: str = ""


@dataclass
class RollbackResult:
    """Result of a rollback operation."""

    success: bool
    previous_version: str = ""
    rolled_back_to: str = ""
    error: str = ""


class BuildAdapter(ABC):
    """Abstract adapter for building container images."""

    provider: str = "unknown"

    @abstractmethod
    def build(self, spec: ServiceSpec, context_path: str = ".") -> BuildResult:
        """Build a container image from source."""
        ...


class RegistryAdapter(ABC):
    """Abstract adapter for pushing images to a container registry."""

    provider: str = "unknown"

    @abstractmethod
    def push(self, image: str, tag: str) -> PushResult:
        """Push a built image to the registry."""
        ...

    @abstractmethod
    def image_uri(self, name: str, tag: str) -> str:
        """Return the full image URI for this registry."""
        ...


class ClusterAdapter(ABC):
    """Abstract adapter for deploying to a Kubernetes cluster."""

    provider: str = "unknown"

    @abstractmethod
    def deploy(self, spec: ServiceSpec, image_uri: str) -> DeployResult:
        """Deploy a service to the cluster."""
        ...

    @abstractmethod
    def validate(self, spec: ServiceSpec) -> ValidationResult:
        """Validate a deployed service (health checks, readiness)."""
        ...

    @abstractmethod
    def rollback(self, spec: ServiceSpec) -> RollbackResult:
        """Rollback to the previous version."""
        ...

    @abstractmethod
    def status(self, spec: ServiceSpec) -> DeployResult:
        """Get current deployment status."""
        ...


@dataclass
class DeploymentAdapters:
    """Bundle of adapters for a specific provider."""

    provider: str
    build: BuildAdapter
    registry: RegistryAdapter
    cluster: ClusterAdapter
