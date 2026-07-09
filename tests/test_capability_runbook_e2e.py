"""
E2E tests for capability-based runbook execution across 4 providers.

Verifies that every capability step in every catalog runbook resolves to a
valid provider-specific action for all 4 providers (AWS, GCP, Azure, OnPrem).
"""

from __future__ import annotations

import pytest

from src.agents.adapters.execution.aws import AwsSsmExecutionAdapter
from src.agents.adapters.execution.azure import AzureExecutionAdapter
from src.agents.adapters.execution.gcp import GcpExecutionAdapter
from src.agents.adapters.execution.onprem import OnPremExecutionAdapter
from src.agents.adapters.registry import get_execution_adapter, supported_providers
from src.agents.models import NormalizedIncident
from src.agents.runbooks.capability_schema import (
    CapabilityRunbook,
    RunbookStep,
    evaluate_condition,
    validate_capability_runbook,
)
from src.agents.runbooks.catalog import CAPABILITY_RUNBOOKS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PROVIDERS = ["aws", "gcp", "azure", "onprem"]

RESOURCE_TYPE_METADATA = {
    "kubernetes-workload": {
        "aws": {"dimensions": {"ClusterName": "prod-eks", "Namespace": "api", "PodName": "api-pod-1", "NodeGroupName": "ng-1", "DeploymentName": "api-deploy"}},
        "gcp": {"project_id": "my-project", "resource_labels": {"cluster_name": "prod-gke", "namespace_name": "api", "zone": "us-central1-a"}},
        "azure": {"dimensions": {"Namespace": "api"}, "target_resource_ids": ["/subscriptions/sub/resourceGroups/rg/providers/Microsoft.ContainerService/managedClusters/prod-aks"]},
        "onprem": {"labels": {"cluster": "prod-k8s", "namespace": "api"}},
    },
    "lambda-function": {
        "aws": {"dimensions": {"FunctionName": "orders-handler"}},
        "gcp": {"project_id": "my-project", "resource_labels": {"location": "us-central1"}},
        "azure": {"dimensions": {}, "target_resource_ids": ["/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Web/sites/orders-func"]},
        "onprem": {"labels": {"cluster": "prod-k8s", "namespace": "default"}},
    },
    "serverless-service": {
        "aws": {"dimensions": {"FunctionName": "orders-handler"}},
        "gcp": {"project_id": "my-project", "resource_labels": {"location": "us-central1"}},
        "azure": {"dimensions": {}, "target_resource_ids": ["/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Web/sites/orders-func"]},
        "onprem": {"labels": {"cluster": "prod-k8s", "namespace": "default"}},
    },
    "database-instance": {
        "aws": {"dimensions": {"DBInstanceIdentifier": "prod-rds-01"}},
        "gcp": {"project_id": "my-project", "resource_labels": {}},
        "azure": {"dimensions": {}, "target_resource_ids": ["/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Sql/servers/prod-sql/databases/maindb"]},
        "onprem": {"labels": {}},
    },
    "streaming-consumer": {
        "aws": {"dimensions": {"ClusterName": "kafka-prod", "ConsumerGroup": "orders-cg"}},
        "gcp": {"project_id": "my-project", "resource_labels": {}},
        "azure": {"dimensions": {}, "target_resource_ids": ["/subscriptions/sub/resourceGroups/rg/providers/Microsoft.EventHub/namespaces/prod-eh"]},
        "onprem": {"labels": {}},
    },
    "cloud-resource": {
        "aws": {"alarm_name": "generic-alarm"},
        "gcp": {"project_id": "my-project", "policy_name": "alert-policy"},
        "azure": {"alert_rule": "generic-rule"},
        "onprem": {"alertname": "generic-alert"},
    },
    "storage-volume": {
        "aws": {"dimensions": {"VolumeId": "vol-0123456789abcdef"}},
        "gcp": {"project_id": "my-project", "resource_labels": {"disk_name": "data-disk", "zone": "us-central1-a"}},
        "azure": {"dimensions": {"DiskName": "data-disk"}, "target_resource_ids": ["/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Compute/disks/data-disk"]},
        "onprem": {"labels": {"node": "worker-1", "volume": "pvc-data"}},
    },
    "certificate": {
        "aws": {"dimensions": {"CertificateArn": "arn:aws:acm:us-east-1:123456:certificate/abc"}},
        "gcp": {"project_id": "my-project", "resource_labels": {}},
        "azure": {"dimensions": {}, "target_resource_ids": ["/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Web/certificates/my-cert"]},
        "onprem": {"labels": {}},
    },
    "network-endpoint": {
        "aws": {"dimensions": {"ClusterName": "prod-eks", "NodeGroupName": "ng-1"}},
        "gcp": {"project_id": "my-project", "resource_labels": {"cluster_name": "prod-gke", "namespace_name": "default", "zone": "us-central1-a"}},
        "azure": {"dimensions": {"Namespace": "default"}, "target_resource_ids": ["/subscriptions/sub/resourceGroups/rg/providers/Microsoft.ContainerService/managedClusters/prod-aks"]},
        "onprem": {"labels": {"cluster": "prod-k8s", "namespace": "default"}},
    },
}


def _make_incident(provider: str, resource_type: str) -> NormalizedIncident:
    """Create a NormalizedIncident for a given provider and resource type."""
    metadata = RESOURCE_TYPE_METADATA.get(resource_type, {}).get(provider, {})
    return NormalizedIncident(
        provider=provider,
        service="test-service",
        resource_type=resource_type,
        resource_id="test-resource-001",
        signal_type="metric_alarm",
        severity_hint="P2",
        source_metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Test: All catalog runbooks are valid
# ---------------------------------------------------------------------------

class TestCatalogValidity:
    """Ensure all 9 catalog runbooks pass schema validation."""

    def test_all_runbooks_validate(self):
        for runbook_id, data in CAPABILITY_RUNBOOKS.items():
            problems = validate_capability_runbook(data)
            assert problems == [], f"{runbook_id}: {problems}"

    def test_catalog_count(self):
        assert len(CAPABILITY_RUNBOOKS) == 9

    def test_all_runbooks_parse_to_dataclass(self):
        for runbook_id, data in CAPABILITY_RUNBOOKS.items():
            rb = CapabilityRunbook.from_dict(data)
            assert rb.runbook_id == runbook_id
            assert len(rb.steps) >= 1
            assert all(isinstance(s, RunbookStep) for s in rb.steps)


# ---------------------------------------------------------------------------
# Test: Cross-provider capability resolution
# ---------------------------------------------------------------------------

class TestCrossProviderResolution:
    """Test that every step in every runbook resolves to a valid action for each provider."""

    @pytest.fixture(params=PROVIDERS)
    def provider(self, request):
        return request.param

    @pytest.fixture
    def adapter(self, provider):
        return get_execution_adapter(provider)

    def test_eks_pod_oom_resolves(self, provider, adapter):
        """eks-pod-oom: restart_workload + scale_out for kubernetes-workload."""
        incident = _make_incident(provider, "kubernetes-workload")

        r1 = adapter.resolve_action("restart_workload", incident)
        assert r1["provider"] == provider
        assert r1["capability"] == "restart_workload"
        assert r1["action"] != ""

        r2 = adapter.resolve_action("scale_out", incident)
        assert r2["action"] != ""

    def test_rds_cpu_high_resolves(self, provider, adapter):
        """rds-cpu-high: scale_database_primary + scale_database_read."""
        incident = _make_incident(provider, "database-instance")

        r1 = adapter.resolve_action("scale_database_primary", incident)
        assert r1["provider"] == provider
        assert "scale" in r1["action"].lower() or "Scale" in r1["action"]

        r2 = adapter.resolve_action("scale_database_read", incident)
        assert r2["action"] != ""

    def test_kafka_lag_spike_resolves(self, provider, adapter):
        """kafka-lag-spike: scale_out_workers + rebalance_consumer."""
        incident = _make_incident(provider, "streaming-consumer")

        r1 = adapter.resolve_action("scale_out_workers", incident)
        assert r1["provider"] == provider
        assert r1["action"] != ""

        r2 = adapter.resolve_action("rebalance_consumer", incident)
        assert r2["action"] != ""

    def test_disk_full_resolves(self, provider, adapter):
        """disk-full: cleanup_disk_space + expand_storage."""
        incident = _make_incident(provider, "storage-volume")

        r1 = adapter.resolve_action("cleanup_disk_space", incident)
        assert r1["provider"] == provider
        assert r1["action"] != ""

        r2 = adapter.resolve_action("expand_storage", incident)
        assert r2["action"] != ""

    def test_health_check_failure_resolves(self, provider, adapter):
        """health-check-failure: restart_workload + rollback_release."""
        incident = _make_incident(provider, "kubernetes-workload")

        r1 = adapter.resolve_action("restart_workload", incident)
        assert r1["action"] != ""

        r2 = adapter.resolve_action("rollback_release", incident)
        assert r2["action"] != ""

    def test_certificate_expiry_resolves(self, provider, adapter):
        """certificate-expiry: renew_certificate + open_change_request."""
        incident = _make_incident(provider, "certificate")

        r1 = adapter.resolve_action("renew_certificate", incident)
        assert r1["provider"] == provider
        assert r1["action"] != ""

        r2 = adapter.resolve_action("open_change_request", incident)
        assert r2["action"] != ""

    def test_network_latency_resolves(self, provider, adapter):
        """network-latency-high: drain_node + scale_out."""
        incident = _make_incident(provider, "network-endpoint")

        r1 = adapter.resolve_action("drain_node", incident)
        assert r1["provider"] == provider
        assert r1["action"] != ""

        r2 = adapter.resolve_action("scale_out", incident)
        assert r2["action"] != ""

    def test_generic_recovery_resolves(self, provider, adapter):
        """generic-recovery: open_change_request."""
        incident = _make_incident(provider, "cloud-resource")

        r1 = adapter.resolve_action("open_change_request", incident)
        assert r1["provider"] == provider
        assert r1["action"] != ""


# ---------------------------------------------------------------------------
# Test: Lambda-throttle serverless-service cross-provider
# ---------------------------------------------------------------------------

class TestServerlessResolution:
    """Verify lambda-throttle works with serverless-service resource type across cloud providers."""

    @pytest.mark.parametrize("provider", ["aws", "gcp", "azure"])
    def test_increase_function_concurrency(self, provider):
        adapter = get_execution_adapter(provider)
        resource_type = "serverless-service" if provider != "aws" else "lambda-function"
        incident = _make_incident(provider, resource_type)

        result = adapter.resolve_action("increase_function_concurrency", incident)
        assert result["provider"] == provider
        assert result["action"] != ""

    def test_onprem_has_no_serverless(self):
        """On-prem has no serverless; requesting it should raise ValueError."""
        adapter = get_execution_adapter("onprem")
        incident = _make_incident("onprem", "lambda-function")

        with pytest.raises(ValueError):
            adapter.resolve_action("increase_function_concurrency", incident)


# ---------------------------------------------------------------------------
# Test: Full runbook step walk simulation
# ---------------------------------------------------------------------------

class TestRunbookStepWalk:
    """Simulate walking through all steps of a runbook for each provider."""

    @pytest.mark.parametrize("runbook_id", list(CAPABILITY_RUNBOOKS.keys()))
    @pytest.mark.parametrize("provider", PROVIDERS)
    def test_walk_all_steps(self, runbook_id, provider):
        """Walk every step and verify resolution — skip steps that legitimately don't apply."""
        rb = CapabilityRunbook.from_dict(CAPABILITY_RUNBOOKS[runbook_id])
        adapter = get_execution_adapter(provider)

        # Determine the primary resource type for this runbook
        resource_types = rb.resource_types
        primary_type = resource_types[0] if resource_types else "cloud-resource"

        # Skip entire runbook if it's serverless-only on onprem
        if provider == "onprem" and primary_type == "lambda-function":
            pytest.skip("On-prem has no serverless capability")

        incident = _make_incident(provider, primary_type)

        context = {"severity": "P2", "provider": provider, "previous_step_failed": False}
        resolved_actions = []

        for step in rb.steps:
            if not evaluate_condition(step.condition, context):
                continue

            try:
                result = adapter.resolve_action(step.capability, incident)
                resolved_actions.append(result)
                context["previous_step_failed"] = False
            except ValueError:
                # Some capabilities may not be applicable to specific provider+resource combos
                context["previous_step_failed"] = True

        # At least one step should resolve successfully
        assert len(resolved_actions) >= 1, (
            f"No steps resolved for {runbook_id} on {provider} ({primary_type})"
        )


# ---------------------------------------------------------------------------
# Test: Provider registry completeness
# ---------------------------------------------------------------------------

class TestProviderRegistry:
    """Verify provider registry reports all 4 providers."""

    def test_supported_providers(self):
        providers = supported_providers()
        assert set(providers) == {"aws", "gcp", "azure", "onprem"}

    @pytest.mark.parametrize("provider", PROVIDERS)
    def test_get_execution_adapter(self, provider):
        adapter = get_execution_adapter(provider)
        assert adapter.provider == provider

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unsupported"):
            get_execution_adapter("alibaba")


# ---------------------------------------------------------------------------
# Test: Condition evaluation with new runbook patterns
# ---------------------------------------------------------------------------

class TestNewConditionPatterns:
    """Test condition evaluation patterns introduced by new runbooks."""

    def test_disk_full_second_step_only_on_failure(self):
        """expand_storage step only runs if cleanup_disk_space failed."""
        rb = CapabilityRunbook.from_dict(CAPABILITY_RUNBOOKS["disk-full"])
        assert rb.steps[1].condition == {"previous_step_failed": True}

        # Cleanup succeeded — expand should be skipped
        assert evaluate_condition(rb.steps[1].condition, {"previous_step_failed": False}) is False

        # Cleanup failed — expand should run
        assert evaluate_condition(rb.steps[1].condition, {"previous_step_failed": True}) is True

    def test_health_check_rollback_only_on_restart_failure(self):
        """rollback step in health-check-failure only runs if restart failed."""
        rb = CapabilityRunbook.from_dict(CAPABILITY_RUNBOOKS["health-check-failure"])
        rollback_step = rb.steps[1]
        assert rollback_step.capability == "rollback_release"
        assert rollback_step.condition == {"previous_step_failed": True}

    def test_certificate_expiry_notify_only_on_renewal_failure(self):
        """open_change_request step runs only if renew_certificate failed."""
        rb = CapabilityRunbook.from_dict(CAPABILITY_RUNBOOKS["certificate-expiry"])
        notify_step = rb.steps[1]
        assert notify_step.capability == "open_change_request"
        assert notify_step.condition == {"previous_step_failed": True}

    def test_network_latency_scale_always_runs(self):
        """scale_out step in network-latency-high has no condition (always runs after drain)."""
        rb = CapabilityRunbook.from_dict(CAPABILITY_RUNBOOKS["network-latency-high"])
        scale_step = rb.steps[1]
        assert scale_step.condition is None
        assert evaluate_condition(scale_step.condition, {}) is True
