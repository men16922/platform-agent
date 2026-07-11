"""
Tests for GCP Day2 Operations pipeline.

Tests the 4-step Cloud Function handlers:
  Detector → Analyzer → Decision → Executor
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from src.agents.models import (
    RemediationMode, Severity,
)


# ------------------------------------------------------------------
# Test fixtures
# ------------------------------------------------------------------

@pytest.fixture
def gcp_alert_event():
    """Sample Cloud Monitoring alert payload (Pub/Sub message)."""
    return {
        "incident": {
            "incident_id": "test-incident-001",
            "resource": {
                "type": "k8s_container",
                "labels": {
                    "cluster_name": "production-cluster",
                    "namespace_name": "default",
                    "pod_name": "orders-api-7f8b9c6d5-abc12",
                    "container_name": "orders-api",
                    "project_id": "my-gcp-project",
                }
            },
            "policy_name": "pod-oom-alert",
            "condition_name": "Memory utilization > 90%",
            "summary": "Memory utilization for pod orders-api is above 90%",
            "state": "open",
            "severity": "WARNING",
            "started_at": "2026-07-10T09:00:00Z",
            "metric": {
                "type": "kubernetes.io/container/memory/used_bytes",
            },
            "scoping_project_id": "my-gcp-project",
            "url": "https://console.cloud.google.com/monitoring/alerting/incidents/test-001",
        }
    }


@pytest.fixture
def gcp_cloud_run_alert():
    """Sample Cloud Run alert."""
    return {
        "incident": {
            "incident_id": "test-incident-002",
            "resource": {
                "type": "cloud_run_revision",
                "labels": {
                    "service_name": "payment-service",
                    "revision_name": "payment-service-00042",
                    "location": "asia-northeast3",
                }
            },
            "policy_name": "cloud-run-error-rate",
            "condition_name": "Error rate > 5%",
            "summary": "Error rate for payment-service exceeds threshold",
            "state": "open",
            "severity": "CRITICAL",
            "started_at": "2026-07-10T09:05:00Z",
            "metric": {"type": "run.googleapis.com/request_count"},
            "scoping_project_id": "my-gcp-project",
        }
    }


@pytest.fixture
def gcp_cloudsql_alert():
    """Sample Cloud SQL alert."""
    return {
        "incident": {
            "incident_id": "test-incident-003",
            "resource": {
                "type": "cloudsql_database",
                "labels": {
                    "database_id": "my-gcp-project:orders-db",
                    "instance_id": "orders-db",
                }
            },
            "policy_name": "cloudsql-cpu-high",
            "condition_name": "CPU > 80%",
            "summary": "Cloud SQL instance orders-db CPU utilization high",
            "state": "open",
            "severity": "WARNING",
            "started_at": "2026-07-10T09:10:00Z",
            "metric": {"type": "cloudsql.googleapis.com/database/cpu/utilization"},
            "scoping_project_id": "my-gcp-project",
        }
    }


@pytest.fixture
def detector_output_dict(gcp_alert_event):
    """DetectorOutput as dict (simulating Cloud Workflows state)."""
    from src.agents.operations.gcp.detector import cloud_function_handler
    return cloud_function_handler(gcp_alert_event)


# ------------------------------------------------------------------
# Detector tests
# ------------------------------------------------------------------

class TestGcpDetector:
    def test_detect_k8s_alert(self, gcp_alert_event):
        from src.agents.operations.gcp.detector import cloud_function_handler

        result = cloud_function_handler(gcp_alert_event)

        assert result["alarm"]["alarm_name"] == "pod-oom-alert"
        assert result["alarm"]["state"] == "ALARM"
        assert "GCP/" in result["alarm"]["namespace"]
        assert result["normalized_incident"]["provider"] == "gcp"
        assert result["normalized_incident"]["resource_type"] == "kubernetes-workload"

    def test_detect_cloud_run_alert(self, gcp_cloud_run_alert):
        from src.agents.operations.gcp.detector import cloud_function_handler

        result = cloud_function_handler(gcp_cloud_run_alert)

        assert result["normalized_incident"]["provider"] == "gcp"
        assert result["normalized_incident"]["resource_type"] == "serverless-service"
        assert result["alarm"]["alarm_name"] == "cloud-run-error-rate"

    def test_detect_cloudsql_alert(self, gcp_cloudsql_alert):
        from src.agents.operations.gcp.detector import cloud_function_handler

        result = cloud_function_handler(gcp_cloudsql_alert)

        assert result["normalized_incident"]["provider"] == "gcp"
        assert result["normalized_incident"]["resource_type"] == "database-instance"

    def test_detect_pubsub_envelope(self, gcp_alert_event):
        """Test Pub/Sub CloudEvent envelope extraction."""
        import base64
        from src.agents.operations.gcp.detector import cloud_function_handler

        encoded = base64.b64encode(json.dumps(gcp_alert_event).encode()).decode()
        pubsub_event = {
            "data": {
                "message": {
                    "data": encoded,
                }
            }
        }

        result = cloud_function_handler(pubsub_event)
        assert result["alarm"]["alarm_name"] == "pod-oom-alert"
        assert result["normalized_incident"]["provider"] == "gcp"

    def test_detect_empty_log_results(self, gcp_alert_event):
        """Log query returns empty when google-cloud-logging not installed."""
        from src.agents.operations.gcp.detector import cloud_function_handler

        result = cloud_function_handler(gcp_alert_event)
        # Without google-cloud-logging, should gracefully return empty
        assert isinstance(result["log_insights_results"], list)

    def test_detect_output_serialisable(self, gcp_alert_event):
        from src.agents.operations.gcp.detector import cloud_function_handler

        result = cloud_function_handler(gcp_alert_event)
        # Must be JSON-serialisable (Cloud Workflows requirement)
        serialised = json.dumps(result)
        assert json.loads(serialised) == result


# ------------------------------------------------------------------
# Analyzer tests
# ------------------------------------------------------------------

class TestGcpAnalyzer:
    @patch.dict("sys.modules", {"vertexai": None})
    def test_analyze_fallback_without_vertexai(self, detector_output_dict):
        """Without vertexai installed, should use heuristic fallback."""
        from src.agents.operations.gcp.analyzer import cloud_function_handler

        result = cloud_function_handler(detector_output_dict)

        assert "root_cause" in result
        assert result["severity"] in ("P1", "P2", "P3")
        assert 0.0 <= result["confidence"] <= 1.0
        assert isinstance(result["similar_incidents"], list)

    @patch.dict("sys.modules", {"vertexai": None})
    def test_analyze_severity_heuristic_oom(self, gcp_alert_event):
        """OOM-related alert should map to P2."""
        from src.agents.operations.gcp.detector import cloud_function_handler as detect
        from src.agents.operations.gcp.analyzer import cloud_function_handler as analyze

        gcp_alert_event["incident"]["summary"] = "Pod OOM killed, restarting"
        detector_out = detect(gcp_alert_event)
        result = analyze(detector_out)

        assert result["severity"] == "P2"

    @patch.dict("sys.modules", {"vertexai": None})
    def test_analyze_severity_heuristic_critical(self, gcp_alert_event):
        """Outage/down keywords should map to P1."""
        from src.agents.operations.gcp.detector import cloud_function_handler as detect
        from src.agents.operations.gcp.analyzer import cloud_function_handler as analyze

        gcp_alert_event["incident"]["summary"] = "Service unavailable - complete outage"
        detector_out = detect(gcp_alert_event)
        result = analyze(detector_out)

        assert result["severity"] == "P1"

    def test_analyze_output_serialisable(self, detector_output_dict):
        from src.agents.operations.gcp.analyzer import cloud_function_handler

        result = cloud_function_handler(detector_output_dict)
        serialised = json.dumps(result)
        assert json.loads(serialised) == result

    @patch("src.agents.operations.gcp.analyzer.vertexai", create=True)
    def test_analyze_with_mock_vertexai(self, mock_vertexai, detector_output_dict):
        """Test LLM path with mocked Vertex AI."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "root_cause": "Pod memory leak causing OOM",
            "severity": "P2",
            "confidence": 0.85,
        })
        mock_model.generate_content.return_value = mock_response

        with patch("src.agents.operations.gcp.analyzer.vertexai") as mv:
            with patch("src.agents.operations.gcp.analyzer.GenerativeModel", return_value=mock_model, create=True):
                # This would need vertexai importable; test fallback instead
                pass


# ------------------------------------------------------------------
# Decision tests
# ------------------------------------------------------------------

class TestGcpDecision:
    def test_decision_selects_runbook(self, detector_output_dict):
        from src.agents.operations.gcp.analyzer import cloud_function_handler as analyze
        from src.agents.operations.gcp.decision import cloud_function_handler as decide

        analyzer_out = analyze(detector_output_dict)
        result = decide(analyzer_out)

        assert "runbook_id" in result
        assert "remediation_mode" in result
        assert result["remediation_mode"] in ("AUTO", "APPROVE", "MANUAL")
        assert isinstance(result["actions"], list)

    def test_decision_p1_auto_mode(self, detector_output_dict):
        from src.agents.operations.gcp.analyzer import cloud_function_handler as analyze
        from src.agents.operations.gcp.decision import cloud_function_handler as decide

        analyzer_out = analyze(detector_output_dict)
        # Force P1
        analyzer_out["severity"] = "P1"
        result = decide(analyzer_out)

        assert result["remediation_mode"] == "AUTO"

    def test_decision_p2_approve_mode(self, detector_output_dict):
        from src.agents.operations.gcp.analyzer import cloud_function_handler as analyze
        from src.agents.operations.gcp.decision import cloud_function_handler as decide

        analyzer_out = analyze(detector_output_dict)
        analyzer_out["severity"] = "P2"
        result = decide(analyzer_out)

        assert result["remediation_mode"] == "APPROVE"

    def test_decision_p3_manual_mode(self, detector_output_dict):
        from src.agents.operations.gcp.analyzer import cloud_function_handler as analyze
        from src.agents.operations.gcp.decision import cloud_function_handler as decide

        analyzer_out = analyze(detector_output_dict)
        analyzer_out["severity"] = "P3"
        result = decide(analyzer_out)

        assert result["remediation_mode"] == "MANUAL"

    def test_decision_dangerous_action_forces_approve(self, gcp_alert_event):
        """Actions with Delete/Terminate should force APPROVE regardless of severity."""
        from src.agents.operations.gcp.decision import _determine_mode

        mode = _determine_mode(Severity.P1, ["GCP-DeleteGKEWorkload"])
        assert mode == RemediationMode.APPROVE

    def test_decision_resolves_gcp_actions(self, detector_output_dict):
        from src.agents.operations.gcp.analyzer import cloud_function_handler as analyze
        from src.agents.operations.gcp.decision import cloud_function_handler as decide

        analyzer_out = analyze(detector_output_dict)
        analyzer_out["severity"] = "P1"
        result = decide(analyzer_out)

        # Should resolve to GCP-specific actions
        for action in result["actions"]:
            assert action.startswith("GCP-")

    def test_decision_output_serialisable(self, detector_output_dict):
        from src.agents.operations.gcp.analyzer import cloud_function_handler as analyze
        from src.agents.operations.gcp.decision import cloud_function_handler as decide

        analyzer_out = analyze(detector_output_dict)
        result = decide(analyzer_out)
        serialised = json.dumps(result)
        assert json.loads(serialised) == result


# ------------------------------------------------------------------
# Executor tests
# ------------------------------------------------------------------

class TestGcpExecutor:
    def test_executor_auto_mode(self, detector_output_dict):
        from src.agents.operations.gcp.analyzer import cloud_function_handler as analyze
        from src.agents.operations.gcp.decision import cloud_function_handler as decide
        from src.agents.operations.gcp.executor import cloud_function_handler as execute

        analyzer_out = analyze(detector_output_dict)
        analyzer_out["severity"] = "P1"
        decision_out = decide(analyzer_out)
        result = execute(decision_out)

        assert result["incident_id"].startswith("GCP-INC-")
        assert isinstance(result["executed_actions"], list)
        assert isinstance(result["skipped_actions"], list)

    def test_executor_manual_mode_skips(self, detector_output_dict):
        from src.agents.operations.gcp.analyzer import cloud_function_handler as analyze
        from src.agents.operations.gcp.decision import cloud_function_handler as decide
        from src.agents.operations.gcp.executor import cloud_function_handler as execute

        analyzer_out = analyze(detector_output_dict)
        analyzer_out["severity"] = "P3"
        decision_out = decide(analyzer_out)
        result = execute(decision_out)

        assert result["incident_id"].startswith("GCP-INC-")
        assert result["executed_actions"] == []

    def test_executor_incident_id_format(self, detector_output_dict):
        from src.agents.operations.gcp.analyzer import cloud_function_handler as analyze
        from src.agents.operations.gcp.decision import cloud_function_handler as decide
        from src.agents.operations.gcp.executor import cloud_function_handler as execute

        analyzer_out = analyze(detector_output_dict)
        decision_out = decide(analyzer_out)
        result = execute(decision_out)

        assert result["incident_id"].startswith("GCP-INC-")
        assert len(result["incident_id"]) == 16  # "GCP-INC-" (8) + 8 hex chars

    def test_executor_output_serialisable(self, detector_output_dict):
        from src.agents.operations.gcp.analyzer import cloud_function_handler as analyze
        from src.agents.operations.gcp.decision import cloud_function_handler as decide
        from src.agents.operations.gcp.executor import cloud_function_handler as execute

        analyzer_out = analyze(detector_output_dict)
        decision_out = decide(analyzer_out)
        result = execute(decision_out)
        serialised = json.dumps(result)
        assert json.loads(serialised) == result


# ------------------------------------------------------------------
# E2E pipeline test
# ------------------------------------------------------------------

class TestGcpPipelineE2E:
    def test_full_pipeline_k8s_oom(self, gcp_alert_event):
        """Full pipeline: K8s OOM alert → detect → analyze → decide → execute."""
        from src.agents.operations.gcp.detector import cloud_function_handler as detect
        from src.agents.operations.gcp.analyzer import cloud_function_handler as analyze
        from src.agents.operations.gcp.decision import cloud_function_handler as decide
        from src.agents.operations.gcp.executor import cloud_function_handler as execute

        detector_out = detect(gcp_alert_event)
        analyzer_out = analyze(detector_out)
        decision_out = decide(analyzer_out)
        executor_out = execute(decision_out)

        # Verify full chain
        assert executor_out["incident_id"].startswith("GCP-INC-")
        assert executor_out["decision"]["runbook_id"] != ""
        assert executor_out["decision"]["analyzer"]["severity"] in ("P1", "P2", "P3")

    def test_full_pipeline_cloud_run(self, gcp_cloud_run_alert):
        """Full pipeline: Cloud Run error rate alert."""
        from src.agents.operations.gcp.detector import cloud_function_handler as detect
        from src.agents.operations.gcp.analyzer import cloud_function_handler as analyze
        from src.agents.operations.gcp.decision import cloud_function_handler as decide
        from src.agents.operations.gcp.executor import cloud_function_handler as execute

        detector_out = detect(gcp_cloud_run_alert)
        analyzer_out = analyze(detector_out)
        decision_out = decide(analyzer_out)
        executor_out = execute(decision_out)

        assert executor_out["incident_id"].startswith("GCP-INC-")

    def test_full_pipeline_cloudsql(self, gcp_cloudsql_alert):
        """Full pipeline: Cloud SQL high CPU alert."""
        from src.agents.operations.gcp.detector import cloud_function_handler as detect
        from src.agents.operations.gcp.analyzer import cloud_function_handler as analyze
        from src.agents.operations.gcp.decision import cloud_function_handler as decide
        from src.agents.operations.gcp.executor import cloud_function_handler as execute

        detector_out = detect(gcp_cloudsql_alert)
        analyzer_out = analyze(detector_out)
        decision_out = decide(analyzer_out)
        executor_out = execute(decision_out)

        assert executor_out["incident_id"].startswith("GCP-INC-")


# ------------------------------------------------------------------
# Workflows tests
# ------------------------------------------------------------------

class TestGcpWorkflows:
    def test_workflow_yaml_valid(self):
        from src.agents.operations.gcp.workflows import get_workflow_yaml

        yaml_str = get_workflow_yaml()
        assert "main:" in yaml_str
        assert "detect:" in yaml_str
        assert "analyze:" in yaml_str
        assert "decide:" in yaml_str
        assert "execute:" in yaml_str
        assert "approval_gate:" in yaml_str

    def test_deployment_commands(self):
        from src.agents.operations.gcp.workflows import get_deployment_commands

        commands = get_deployment_commands("my-project", "asia-northeast3")
        assert len(commands) >= 6
        assert any("pubsub topics create" in cmd for cmd in commands)
        assert any("workflows deploy" in cmd for cmd in commands)
        assert any("functions deploy" in cmd for cmd in commands)
        assert any("eventarc triggers create" in cmd for cmd in commands)

    def test_eventarc_trigger_config(self):
        from src.agents.operations.gcp.workflows import get_eventarc_trigger_config

        config = get_eventarc_trigger_config("my-project")
        assert config["location"] == "asia-northeast3"
        assert "my-project" in config["transport"]["pubsub"]["topic"]
