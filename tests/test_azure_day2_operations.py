"""
Tests for Azure Day2 Operations pipeline.

Tests the 4-step Azure Function handlers:
  Detector → Analyzer → Decision → Executor
"""

import json
import pytest

from src.agents.models import (
    AlarmContext, AnalyzerOutput, DecisionOutput, DetectorOutput,
    ExecutorOutput, NormalizedIncident, RemediationMode, Severity,
)


# ------------------------------------------------------------------
# Test fixtures
# ------------------------------------------------------------------

@pytest.fixture
def azure_aks_alert():
    """Sample Azure Monitor alert (AKS pod issue, Common Alert Schema)."""
    return {
        "schemaId": "azureMonitorCommonAlertSchema",
        "data": {
            "essentials": {
                "alertId": "/subscriptions/sub-123/providers/Microsoft.AlertsManagement/alerts/alert-001",
                "alertRule": "aks-pod-oom-alert",
                "severity": "Sev2",
                "signalType": "Metric",
                "monitorCondition": "Fired",
                "targetResourceType": "Microsoft.ContainerService/managedClusters",
                "alertTargetIDs": [
                    "/subscriptions/sub-123/resourceGroups/rg-prod/providers/Microsoft.ContainerService/managedClusters/aks-prod"
                ],
                "description": "Pod memory usage exceeded 90%",
                "firedDateTime": "2026-07-10T09:00:00Z",
            },
            "alertContext": {
                "condition": {
                    "allOf": [
                        {
                            "metricName": "kube_pod_container_resource_requests_memory_bytes",
                            "operator": "GreaterThan",
                            "threshold": "90",
                            "dimensions": [
                                {"name": "Pod", "value": "orders-api-7f8b9c-abc12"},
                                {"name": "Namespace", "value": "default"},
                                {"name": "Deployment", "value": "orders-api"},
                            ]
                        }
                    ]
                }
            }
        }
    }


@pytest.fixture
def azure_function_alert():
    """Sample Azure Function throttling alert."""
    return {
        "schemaId": "azureMonitorCommonAlertSchema",
        "data": {
            "essentials": {
                "alertId": "/subscriptions/sub-123/alerts/alert-002",
                "alertRule": "function-throttle-alert",
                "severity": "Sev2",
                "signalType": "Metric",
                "monitorCondition": "Fired",
                "targetResourceType": "Microsoft.Web/sites",
                "alertTargetIDs": [
                    "/subscriptions/sub-123/resourceGroups/rg-prod/providers/Microsoft.Web/sites/payment-func"
                ],
                "description": "Function execution throttling detected",
                "firedDateTime": "2026-07-10T09:05:00Z",
            },
            "alertContext": {
                "condition": {
                    "allOf": [
                        {
                            "metricName": "Http429",
                            "operator": "GreaterThan",
                            "threshold": "10",
                            "dimensions": [
                                {"name": "FunctionApp", "value": "payment-func"},
                            ]
                        }
                    ]
                }
            }
        }
    }


@pytest.fixture
def azure_sql_alert():
    """Sample Azure SQL CPU alert."""
    return {
        "schemaId": "azureMonitorCommonAlertSchema",
        "data": {
            "essentials": {
                "alertId": "/subscriptions/sub-123/alerts/alert-003",
                "alertRule": "sql-cpu-high-alert",
                "severity": "Sev3",
                "signalType": "Metric",
                "monitorCondition": "Fired",
                "targetResourceType": "Microsoft.Sql/servers/databases",
                "alertTargetIDs": [
                    "/subscriptions/sub-123/resourceGroups/rg-prod/providers/Microsoft.Sql/servers/sql-prod/databases/orders-db"
                ],
                "description": "SQL Database CPU above 80%",
                "firedDateTime": "2026-07-10T09:10:00Z",
            },
            "alertContext": {
                "condition": {
                    "allOf": [
                        {
                            "metricName": "cpu_percent",
                            "operator": "GreaterThan",
                            "threshold": "80",
                            "dimensions": [
                                {"name": "DatabaseName", "value": "orders-db"},
                            ]
                        }
                    ]
                }
            }
        }
    }


@pytest.fixture
def detector_output_dict(azure_aks_alert):
    """DetectorOutput as dict (simulating Durable Functions state)."""
    from src.agents.operations.azure.detector import azure_function_handler
    return azure_function_handler(azure_aks_alert)


# ------------------------------------------------------------------
# Detector tests
# ------------------------------------------------------------------

class TestAzureDetector:
    def test_detect_aks_alert(self, azure_aks_alert):
        from src.agents.operations.azure.detector import azure_function_handler

        result = azure_function_handler(azure_aks_alert)

        assert result["alarm"]["alarm_name"] == "aks-pod-oom-alert"
        assert result["alarm"]["state"] == "ALARM"
        assert "Azure/" in result["alarm"]["namespace"]
        assert result["normalized_incident"]["provider"] == "azure"
        assert result["normalized_incident"]["resource_type"] == "kubernetes-workload"

    def test_detect_function_alert(self, azure_function_alert):
        from src.agents.operations.azure.detector import azure_function_handler

        result = azure_function_handler(azure_function_alert)

        assert result["normalized_incident"]["provider"] == "azure"
        assert result["normalized_incident"]["resource_type"] == "serverless-service"
        assert result["alarm"]["alarm_name"] == "function-throttle-alert"

    def test_detect_sql_alert(self, azure_sql_alert):
        from src.agents.operations.azure.detector import azure_function_handler

        result = azure_function_handler(azure_sql_alert)

        assert result["normalized_incident"]["provider"] == "azure"
        assert result["normalized_incident"]["resource_type"] == "database-instance"

    def test_detect_empty_log_results(self, azure_aks_alert):
        from src.agents.operations.azure.detector import azure_function_handler

        result = azure_function_handler(azure_aks_alert)
        assert isinstance(result["log_insights_results"], list)

    def test_detect_output_serialisable(self, azure_aks_alert):
        from src.agents.operations.azure.detector import azure_function_handler

        result = azure_function_handler(azure_aks_alert)
        serialised = json.dumps(result)
        assert json.loads(serialised) == result

    def test_detect_dimensions_extracted(self, azure_aks_alert):
        from src.agents.operations.azure.detector import azure_function_handler

        result = azure_function_handler(azure_aks_alert)
        dims = result["alarm"]["dimensions"]
        assert "Pod" in dims
        assert "Namespace" in dims


# ------------------------------------------------------------------
# Analyzer tests
# ------------------------------------------------------------------

class TestAzureAnalyzer:
    def test_analyze_fallback_without_openai(self, detector_output_dict):
        """Without openai installed or endpoint configured, should use heuristic fallback."""
        from src.agents.operations.azure.analyzer import azure_function_handler

        result = azure_function_handler(detector_output_dict)

        assert "root_cause" in result
        assert result["severity"] in ("P1", "P2", "P3")
        assert 0.0 <= result["confidence"] <= 1.0
        assert isinstance(result["similar_incidents"], list)

    def test_analyze_severity_heuristic_oom(self, azure_aks_alert):
        from src.agents.operations.azure.detector import azure_function_handler as detect
        from src.agents.operations.azure.analyzer import azure_function_handler as analyze

        azure_aks_alert["data"]["essentials"]["description"] = "Pod OOM killed"
        detector_out = detect(azure_aks_alert)
        result = analyze(detector_out)

        assert result["severity"] == "P2"

    def test_analyze_severity_heuristic_outage(self, azure_aks_alert):
        from src.agents.operations.azure.detector import azure_function_handler as detect
        from src.agents.operations.azure.analyzer import azure_function_handler as analyze

        azure_aks_alert["data"]["essentials"]["description"] = "Service completely unavailable - outage"
        detector_out = detect(azure_aks_alert)
        result = analyze(detector_out)

        assert result["severity"] == "P1"

    def test_analyze_output_serialisable(self, detector_output_dict):
        from src.agents.operations.azure.analyzer import azure_function_handler

        result = azure_function_handler(detector_output_dict)
        serialised = json.dumps(result)
        assert json.loads(serialised) == result


# ------------------------------------------------------------------
# Decision tests
# ------------------------------------------------------------------

class TestAzureDecision:
    def test_decision_selects_runbook(self, detector_output_dict):
        from src.agents.operations.azure.analyzer import azure_function_handler as analyze
        from src.agents.operations.azure.decision import azure_function_handler as decide

        analyzer_out = analyze(detector_output_dict)
        result = decide(analyzer_out)

        assert "runbook_id" in result
        assert "remediation_mode" in result
        assert result["remediation_mode"] in ("AUTO", "APPROVE", "MANUAL")
        assert isinstance(result["actions"], list)

    def test_decision_p1_auto_mode(self, detector_output_dict):
        from src.agents.operations.azure.analyzer import azure_function_handler as analyze
        from src.agents.operations.azure.decision import azure_function_handler as decide

        analyzer_out = analyze(detector_output_dict)
        analyzer_out["severity"] = "P1"
        result = decide(analyzer_out)

        assert result["remediation_mode"] == "AUTO"

    def test_decision_p2_approve_mode(self, detector_output_dict):
        from src.agents.operations.azure.analyzer import azure_function_handler as analyze
        from src.agents.operations.azure.decision import azure_function_handler as decide

        analyzer_out = analyze(detector_output_dict)
        analyzer_out["severity"] = "P2"
        result = decide(analyzer_out)

        assert result["remediation_mode"] == "APPROVE"

    def test_decision_p3_manual_mode(self, detector_output_dict):
        from src.agents.operations.azure.analyzer import azure_function_handler as analyze
        from src.agents.operations.azure.decision import azure_function_handler as decide

        analyzer_out = analyze(detector_output_dict)
        analyzer_out["severity"] = "P3"
        result = decide(analyzer_out)

        assert result["remediation_mode"] == "MANUAL"

    def test_decision_dangerous_action_forces_approve(self):
        from src.agents.operations.azure.decision import _determine_mode

        mode = _determine_mode(Severity.P1, ["AZURE-DeleteAKSWorkload"])
        assert mode == RemediationMode.APPROVE

    def test_decision_resolves_azure_actions(self, detector_output_dict):
        from src.agents.operations.azure.analyzer import azure_function_handler as analyze
        from src.agents.operations.azure.decision import azure_function_handler as decide

        analyzer_out = analyze(detector_output_dict)
        analyzer_out["severity"] = "P1"
        result = decide(analyzer_out)

        for action in result["actions"]:
            assert action.startswith("AZURE-")

    def test_decision_output_serialisable(self, detector_output_dict):
        from src.agents.operations.azure.analyzer import azure_function_handler as analyze
        from src.agents.operations.azure.decision import azure_function_handler as decide

        analyzer_out = analyze(detector_output_dict)
        result = decide(analyzer_out)
        serialised = json.dumps(result)
        assert json.loads(serialised) == result


# ------------------------------------------------------------------
# Executor tests
# ------------------------------------------------------------------

class TestAzureExecutor:
    def test_executor_auto_mode(self, detector_output_dict):
        from src.agents.operations.azure.analyzer import azure_function_handler as analyze
        from src.agents.operations.azure.decision import azure_function_handler as decide
        from src.agents.operations.azure.executor import azure_function_handler as execute

        analyzer_out = analyze(detector_output_dict)
        analyzer_out["severity"] = "P1"
        decision_out = decide(analyzer_out)
        result = execute(decision_out)

        assert result["incident_id"].startswith("AZ-INC-")
        assert isinstance(result["executed_actions"], list)
        assert isinstance(result["skipped_actions"], list)

    def test_executor_manual_mode_skips(self, detector_output_dict):
        from src.agents.operations.azure.analyzer import azure_function_handler as analyze
        from src.agents.operations.azure.decision import azure_function_handler as decide
        from src.agents.operations.azure.executor import azure_function_handler as execute

        analyzer_out = analyze(detector_output_dict)
        analyzer_out["severity"] = "P3"
        decision_out = decide(analyzer_out)
        result = execute(decision_out)

        assert result["incident_id"].startswith("AZ-INC-")
        assert result["executed_actions"] == []

    def test_executor_incident_id_format(self, detector_output_dict):
        from src.agents.operations.azure.analyzer import azure_function_handler as analyze
        from src.agents.operations.azure.decision import azure_function_handler as decide
        from src.agents.operations.azure.executor import azure_function_handler as execute

        analyzer_out = analyze(detector_output_dict)
        decision_out = decide(analyzer_out)
        result = execute(decision_out)

        assert result["incident_id"].startswith("AZ-INC-")
        assert len(result["incident_id"]) == 15  # "AZ-INC-" (7) + 8 hex

    def test_executor_output_serialisable(self, detector_output_dict):
        from src.agents.operations.azure.analyzer import azure_function_handler as analyze
        from src.agents.operations.azure.decision import azure_function_handler as decide
        from src.agents.operations.azure.executor import azure_function_handler as execute

        analyzer_out = analyze(detector_output_dict)
        decision_out = decide(analyzer_out)
        result = execute(decision_out)
        serialised = json.dumps(result)
        assert json.loads(serialised) == result


# ------------------------------------------------------------------
# E2E pipeline test
# ------------------------------------------------------------------

class TestAzurePipelineE2E:
    def test_full_pipeline_aks_oom(self, azure_aks_alert):
        """Full pipeline: AKS pod OOM → detect → analyze → decide → execute."""
        from src.agents.operations.azure.detector import azure_function_handler as detect
        from src.agents.operations.azure.analyzer import azure_function_handler as analyze
        from src.agents.operations.azure.decision import azure_function_handler as decide
        from src.agents.operations.azure.executor import azure_function_handler as execute

        detector_out = detect(azure_aks_alert)
        analyzer_out = analyze(detector_out)
        decision_out = decide(analyzer_out)
        executor_out = execute(decision_out)

        assert executor_out["incident_id"].startswith("AZ-INC-")
        assert executor_out["decision"]["runbook_id"] != ""
        assert executor_out["decision"]["analyzer"]["severity"] in ("P1", "P2", "P3")

    def test_full_pipeline_function_throttle(self, azure_function_alert):
        """Full pipeline: Azure Function throttle alert."""
        from src.agents.operations.azure.detector import azure_function_handler as detect
        from src.agents.operations.azure.analyzer import azure_function_handler as analyze
        from src.agents.operations.azure.decision import azure_function_handler as decide
        from src.agents.operations.azure.executor import azure_function_handler as execute

        detector_out = detect(azure_function_alert)
        analyzer_out = analyze(detector_out)
        decision_out = decide(analyzer_out)
        executor_out = execute(decision_out)

        assert executor_out["incident_id"].startswith("AZ-INC-")

    def test_full_pipeline_sql_cpu(self, azure_sql_alert):
        """Full pipeline: Azure SQL high CPU alert."""
        from src.agents.operations.azure.detector import azure_function_handler as detect
        from src.agents.operations.azure.analyzer import azure_function_handler as analyze
        from src.agents.operations.azure.decision import azure_function_handler as decide
        from src.agents.operations.azure.executor import azure_function_handler as execute

        detector_out = detect(azure_sql_alert)
        analyzer_out = analyze(detector_out)
        decision_out = decide(analyzer_out)
        executor_out = execute(decision_out)

        assert executor_out["incident_id"].startswith("AZ-INC-")


# ------------------------------------------------------------------
# Durable Functions tests
# ------------------------------------------------------------------

class TestAzureDurableFunctions:
    def test_orchestrator_code_valid(self):
        from src.agents.operations.azure.durable_functions import get_orchestrator_code

        code = get_orchestrator_code()
        assert "orchestrator_function" in code
        assert "DetectorActivity" in code
        assert "AnalyzerActivity" in code
        assert "DecisionActivity" in code
        assert "ExecutorActivity" in code
        assert "ApprovalEvent" in code

    def test_activity_codes(self):
        from src.agents.operations.azure.durable_functions import get_activity_codes

        codes = get_activity_codes()
        assert "detector" in codes
        assert "analyzer" in codes
        assert "decision" in codes
        assert "executor" in codes

    def test_function_json_configs(self):
        from src.agents.operations.azure.durable_functions import get_function_json_configs

        configs = get_function_json_configs()
        assert "OrchestratorFunction" in configs
        assert "DetectorActivity" in configs
        assert "EventGridTrigger" in configs
        assert configs["OrchestratorFunction"]["bindings"][0]["type"] == "orchestrationTrigger"
        assert configs["EventGridTrigger"]["bindings"][0]["type"] == "eventGridTrigger"

    def test_deployment_commands(self):
        from src.agents.operations.azure.durable_functions import get_deployment_commands

        commands = get_deployment_commands("rg-platform", "incident-funcs")
        assert len(commands) >= 7
        assert any("group create" in cmd for cmd in commands)
        assert any("cosmosdb create" in cmd for cmd in commands)
        assert any("functionapp create" in cmd for cmd in commands)
        assert any("functionapp publish" in cmd for cmd in commands)
        assert any("eventgrid" in cmd for cmd in commands)
