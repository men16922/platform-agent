"""
GCP Cloud Workflows orchestration definition.

Generates the Cloud Workflows YAML that connects the 4-step pipeline:
  Detector → Analyzer → Decision → Executor

Deployment:
  gcloud workflows deploy incident-response-pipeline \
    --source=workflows.yaml \
    --location=asia-northeast3
"""

from __future__ import annotations

import json
import yaml
from typing import Any


# Cloud Workflows YAML definition
WORKFLOW_YAML = """\
# GCP Day2 Operations — Incident Response Pipeline
# Triggered by: Pub/Sub message from Cloud Monitoring alert
#
# Flow: Detector → Analyzer → Decision → Executor → Report
#
main:
  params: [event]
  steps:
    - init:
        assign:
          - project_id: ${sys.get_env("GCP_PROJECT_ID")}
          - region: ${sys.get_env("GCP_LOCATION", "asia-northeast3")}
          - detector_url: ${sys.get_env("DETECTOR_FUNCTION_URL")}
          - analyzer_url: ${sys.get_env("ANALYZER_FUNCTION_URL")}
          - decision_url: ${sys.get_env("DECISION_FUNCTION_URL")}
          - executor_url: ${sys.get_env("EXECUTOR_FUNCTION_URL")}

    - detect:
        call: http.post
        args:
          url: ${detector_url}
          auth:
            type: OIDC
          body: ${event}
          timeout: 60
        result: detector_output

    - analyze:
        call: http.post
        args:
          url: ${analyzer_url}
          auth:
            type: OIDC
          body: ${detector_output.body}
          timeout: 120
        result: analyzer_output

    - decide:
        call: http.post
        args:
          url: ${decision_url}
          auth:
            type: OIDC
          body: ${analyzer_output.body}
          timeout: 60
        result: decision_output

    - check_mode:
        switch:
          - condition: ${decision_output.body.remediation_mode == "APPROVE"}
            next: approval_gate
          - condition: ${decision_output.body.remediation_mode == "MANUAL"}
            next: execute
        next: execute

    - approval_gate:
        call: events.await_callback
        args:
          callback:
            url: ${sys.get_env("APPROVAL_CALLBACK_URL", "")}
          timeout: 3600
        result: approval_result
        next: check_approval

    - check_approval:
        switch:
          - condition: ${approval_result.body.approved == true}
            next: execute
        next: report_rejected

    - report_rejected:
        call: http.post
        args:
          url: ${executor_url}
          auth:
            type: OIDC
          body:
            $${decision_output.body}
          timeout: 60
        result: executor_output
        next: end

    - execute:
        call: http.post
        args:
          url: ${executor_url}
          auth:
            type: OIDC
          body: ${decision_output.body}
          timeout: 300
        result: executor_output

    - end:
        return: ${executor_output.body}
"""

# Pub/Sub trigger configuration for Eventarc
EVENTARC_TRIGGER_CONFIG = {
    "name": "incident-alert-trigger",
    "location": "asia-northeast3",
    "matching_criteria": [
        {
            "attribute": "type",
            "value": "google.cloud.pubsub.topic.v1.messagePublished",
        }
    ],
    "destination": {
        "workflow": "incident-response-pipeline",
    },
    "transport": {
        "pubsub": {
            "topic": "projects/${PROJECT_ID}/topics/cloud-monitoring-alerts",
        }
    },
}


def get_workflow_yaml() -> str:
    """Return the Cloud Workflows YAML definition."""
    return WORKFLOW_YAML


def get_eventarc_trigger_config(project_id: str, region: str = "asia-northeast3") -> dict[str, Any]:
    """Return Eventarc trigger config with project ID substituted."""
    config = json.loads(json.dumps(EVENTARC_TRIGGER_CONFIG))
    config["transport"]["pubsub"]["topic"] = f"projects/{project_id}/topics/cloud-monitoring-alerts"
    config["location"] = region
    return config


def get_deployment_commands(project_id: str, region: str = "asia-northeast3") -> list[str]:
    """Return gcloud commands to deploy the pipeline."""
    return [
        # 1. Create Pub/Sub topic for alerts
        f"gcloud pubsub topics create cloud-monitoring-alerts --project={project_id}",

        # 2. Deploy Cloud Functions
        f"gcloud functions deploy incident-detector "
        f"--gen2 --runtime=python311 --region={region} "
        f"--trigger-http --allow-unauthenticated=false "
        f"--entry-point=cloud_function_handler "
        f"--source=src/agents/operations/gcp/ "
        f"--project={project_id}",

        f"gcloud functions deploy incident-analyzer "
        f"--gen2 --runtime=python311 --region={region} "
        f"--trigger-http --allow-unauthenticated=false "
        f"--entry-point=cloud_function_handler "
        f"--source=src/agents/operations/gcp/ "
        f"--project={project_id}",

        f"gcloud functions deploy incident-decision "
        f"--gen2 --runtime=python311 --region={region} "
        f"--trigger-http --allow-unauthenticated=false "
        f"--entry-point=cloud_function_handler "
        f"--source=src/agents/operations/gcp/ "
        f"--project={project_id}",

        f"gcloud functions deploy incident-executor "
        f"--gen2 --runtime=python311 --region={region} "
        f"--trigger-http --allow-unauthenticated=false "
        f"--entry-point=cloud_function_handler "
        f"--source=src/agents/operations/gcp/ "
        f"--project={project_id}",

        # 3. Deploy Cloud Workflows
        f"gcloud workflows deploy incident-response-pipeline "
        f"--source=src/agents/operations/gcp/workflows.yaml "
        f"--location={region} "
        f"--project={project_id}",

        # 4. Create Eventarc trigger (Pub/Sub → Workflow)
        f"gcloud eventarc triggers create incident-alert-trigger "
        f"--location={region} "
        f"--destination-workflow=incident-response-pipeline "
        f"--destination-workflow-location={region} "
        f"--event-filters=\"type=google.cloud.pubsub.topic.v1.messagePublished\" "
        f"--transport-topic=cloud-monitoring-alerts "
        f"--project={project_id}",

        # 5. Create Cloud Monitoring notification channel (Pub/Sub)
        f"gcloud beta monitoring channels create "
        f"--type=pubsub "
        f"--display-name='Incident Pipeline Trigger' "
        f"--channel-labels=topic=projects/{project_id}/topics/cloud-monitoring-alerts "
        f"--project={project_id}",
    ]
