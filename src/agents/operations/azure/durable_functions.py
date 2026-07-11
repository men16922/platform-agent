"""
Azure Durable Functions orchestration definition.

Defines the orchestrator that connects the 4-step pipeline:
  Detector → Analyzer → Decision → Executor

Deployment:
  func azure functionapp publish <app-name>

This module provides:
  1. Orchestrator function definition (Python Durable Functions SDK)
  2. Event Grid trigger configuration
  3. Deployment commands
"""

from __future__ import annotations

from typing import Any


# ------------------------------------------------------------------
# Durable Functions Orchestrator (Python SDK pattern)
# ------------------------------------------------------------------

ORCHESTRATOR_CODE = '''\
"""
Azure Durable Functions Orchestrator — Incident Response Pipeline.

Triggered by: Event Grid event from Azure Monitor alert
Flow: Detector → Analyzer → Decision → (Approval?) → Executor
"""

import azure.functions as func
import azure.durable_functions as df


def orchestrator_function(context: df.DurableOrchestrationContext):
    """
    Main orchestrator: chains the 4 activity functions.
    Handles approval gate for P2 severity.
    """
    # Input: Azure Monitor alert event (Common Alert Schema)
    event = context.get_input()

    # Step 1: Detector
    detector_output = yield context.call_activity("DetectorActivity", event)

    # Step 2: Analyzer
    analyzer_output = yield context.call_activity("AnalyzerActivity", detector_output)

    # Step 3: Decision
    decision_output = yield context.call_activity("DecisionActivity", analyzer_output)

    # Step 4: Check mode and execute
    mode = decision_output.get("remediation_mode", "MANUAL")

    if mode == "APPROVE":
        # Wait for external event (Slack approval button)
        import datetime
        approval = yield context.wait_for_external_event(
            "ApprovalEvent",
            timeout=datetime.timedelta(hours=1),
        )
        if not approval or not approval.get("approved"):
            decision_output["remediation_mode"] = "MANUAL"

    # Step 5: Executor
    executor_output = yield context.call_activity("ExecutorActivity", decision_output)

    return executor_output


main = df.Orchestrator.create(orchestrator_function)
'''

# Activity function stubs
DETECTOR_ACTIVITY_CODE = '''\
"""Detector Activity — wraps the detector handler."""

import azure.functions as func
from src.agents.operations.azure.detector import azure_function_handler


def main(event: dict) -> dict:
    return azure_function_handler(event)
'''

ANALYZER_ACTIVITY_CODE = '''\
"""Analyzer Activity — wraps the analyzer handler."""

import azure.functions as func
from src.agents.operations.azure.analyzer import azure_function_handler


def main(event: dict) -> dict:
    return azure_function_handler(event)
'''

DECISION_ACTIVITY_CODE = '''\
"""Decision Activity — wraps the decision handler."""

import azure.functions as func
from src.agents.operations.azure.decision import azure_function_handler


def main(event: dict) -> dict:
    return azure_function_handler(event)
'''

EXECUTOR_ACTIVITY_CODE = '''\
"""Executor Activity — wraps the executor handler."""

import azure.functions as func
from src.agents.operations.azure.executor import azure_function_handler


def main(event: dict) -> dict:
    return azure_function_handler(event)
'''

# Event Grid trigger for starting the orchestrator
EVENT_GRID_TRIGGER_CODE = '''\
"""Event Grid Trigger — starts the Durable Functions orchestrator."""

import azure.functions as func
import azure.durable_functions as df


async def main(event: func.EventGridEvent, starter: str):
    """Start orchestrator when Azure Monitor alert fires."""
    client = df.DurableOrchestrationClient(starter)

    alert_data = event.get_json()
    instance_id = await client.start_new(
        "OrchestratorFunction",
        client_input=alert_data,
    )

    return client.create_check_status_response(None, instance_id)
'''


def get_orchestrator_code() -> str:
    """Return the orchestrator function code."""
    return ORCHESTRATOR_CODE


def get_activity_codes() -> dict[str, str]:
    """Return activity function codes."""
    return {
        "detector": DETECTOR_ACTIVITY_CODE,
        "analyzer": ANALYZER_ACTIVITY_CODE,
        "decision": DECISION_ACTIVITY_CODE,
        "executor": EXECUTOR_ACTIVITY_CODE,
    }


def get_function_json_configs() -> dict[str, dict[str, Any]]:
    """Return function.json configurations for each function."""
    return {
        "OrchestratorFunction": {
            "scriptFile": "__init__.py",
            "bindings": [
                {
                    "name": "context",
                    "type": "orchestrationTrigger",
                    "direction": "in",
                }
            ],
        },
        "DetectorActivity": {
            "scriptFile": "__init__.py",
            "bindings": [
                {
                    "name": "event",
                    "type": "activityTrigger",
                    "direction": "in",
                }
            ],
        },
        "AnalyzerActivity": {
            "scriptFile": "__init__.py",
            "bindings": [
                {
                    "name": "event",
                    "type": "activityTrigger",
                    "direction": "in",
                }
            ],
        },
        "DecisionActivity": {
            "scriptFile": "__init__.py",
            "bindings": [
                {
                    "name": "event",
                    "type": "activityTrigger",
                    "direction": "in",
                }
            ],
        },
        "ExecutorActivity": {
            "scriptFile": "__init__.py",
            "bindings": [
                {
                    "name": "event",
                    "type": "activityTrigger",
                    "direction": "in",
                }
            ],
        },
        "EventGridTrigger": {
            "scriptFile": "__init__.py",
            "bindings": [
                {
                    "name": "event",
                    "type": "eventGridTrigger",
                    "direction": "in",
                },
                {
                    "name": "starter",
                    "type": "durableClient",
                    "direction": "in",
                },
            ],
        },
    }


def get_deployment_commands(
    resource_group: str,
    function_app_name: str,
    location: str = "koreacentral",
) -> list[str]:
    """Return Azure CLI commands to deploy the pipeline."""
    return [
        # 1. Create resource group
        f"az group create --name {resource_group} --location {location}",

        # 2. Create storage account (required for Functions)
        f"az storage account create "
        f"--name {function_app_name.replace('-', '')}store "
        f"--resource-group {resource_group} "
        f"--location {location} --sku Standard_LRS",

        # 3. Create Cosmos DB account (Free tier)
        f"az cosmosdb create "
        f"--name {function_app_name}-cosmos "
        f"--resource-group {resource_group} "
        f"--locations regionName={location} "
        f"--enable-free-tier true",

        # 4. Create Cosmos DB database and containers
        f"az cosmosdb sql database create "
        f"--account-name {function_app_name}-cosmos "
        f"--resource-group {resource_group} "
        f"--name platform-agent",

        f"az cosmosdb sql container create "
        f"--account-name {function_app_name}-cosmos "
        f"--resource-group {resource_group} "
        f"--database-name platform-agent "
        f"--name incident-history "
        f"--partition-key-path /alarm_name",

        f"az cosmosdb sql container create "
        f"--account-name {function_app_name}-cosmos "
        f"--resource-group {resource_group} "
        f"--database-name platform-agent "
        f"--name incident-runbooks "
        f"--partition-key-path /id",

        # 5. Create Function App (Consumption plan)
        f"az functionapp create "
        f"--name {function_app_name} "
        f"--resource-group {resource_group} "
        f"--storage-account {function_app_name.replace('-', '')}store "
        f"--consumption-plan-location {location} "
        f"--runtime python --runtime-version 3.11 "
        f"--functions-version 4",

        # 6. Deploy function app
        f"func azure functionapp publish {function_app_name}",

        # 7. Create Event Grid subscription (Azure Monitor → Function)
        f"az eventgrid event-subscription create "
        f"--name monitor-alert-subscription "
        f"--source-resource-id /subscriptions/{{subscription_id}}/resourceGroups/{resource_group} "
        f"--endpoint-type azurefunction "
        f"--endpoint /subscriptions/{{subscription_id}}/resourceGroups/{resource_group}"
        f"/providers/Microsoft.Web/sites/{function_app_name}"
        f"/functions/EventGridTrigger "
        f"--event-delivery-schema eventgridschema",
    ]
