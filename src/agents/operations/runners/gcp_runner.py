"""
GCP Action Runner.

Handles real GCP API calls for GKE and Cloud Run remediations.
"""

from __future__ import annotations

import base64
import os
import tempfile
import time
from typing import Any

import requests
import structlog

from src.agents.operations.runners import _k8s_rest
from src.agents.operations.runners.gcp_auth import get_gcp_access_token

logger = structlog.get_logger(__name__)


def run_gcp_action(action: str, params: dict[str, list[str]], log: Any) -> None:
    """
    Executes a real GCP remediation action.
    Falls back to mock simulation if GCP_MOCK=True or in testing environment without credentials.
    """
    is_mock = os.getenv("GCP_MOCK", "false").lower() == "true" or os.getenv("TESTING") == "True"
    
    if is_mock:
        log.info("gcp_runner.mock_execution", action=action, params=params)
        time.sleep(1)  # Simulate execution latency
        return

    try:
        token = get_gcp_access_token()
    except Exception as e:
        log.error("gcp_runner.auth_failed", error=str(e))
        raise RuntimeError(f"GCP Authentication failed: {e}")

    if action in {"GCP-RolloutRestartGKEWorkload", "GCP-ScaleGKEWorkload", "GCP-RollbackGKEWorkload"}:
        _run_gke_action(action, params, token, log)
    elif action in {"GCP-ScaleCloudRunService", "GCP-RollbackCloudRunRevision"}:
        _run_cloudrun_action(action, params, token, log)
    else:
        raise ValueError(f"Unsupported GCP action: {action}")


def _run_gke_action(action: str, params: dict[str, list[str]], token: str, log: Any) -> None:
    project_id = params.get("ProjectId", [""])[0]
    cluster_name = params.get("ClusterName", [""])[0]
    namespace = params.get("Namespace", ["default"])[0]
    workload_name = params.get("WorkloadName", [""])[0]

    if not project_id or not cluster_name or not workload_name:
        raise ValueError(f"Missing GKE parameters: ProjectId, ClusterName, and WorkloadName are required. Params: {params}")

    try:
        _execute_gke_call(action, project_id, cluster_name, namespace, workload_name, params, token, log)
    except Exception as exc:
        failover_cluster = os.getenv("GCP_FAILOVER_CLUSTER_NAME") or f"{cluster_name}-backup"
        log.warning(
            "gcp_runner.gke.primary_failed.retry_failover",
            primary_cluster=cluster_name,
            failover_cluster=failover_cluster,
            error=str(exc)
        )
        # Attempt retry on backup failover cluster
        _execute_gke_call(action, project_id, failover_cluster, namespace, workload_name, params, token, log)


def _execute_gke_call(
    action: str, project_id: str, cluster_name: str, namespace: str, workload_name: str,
    params: dict[str, list[str]], token: str, log: Any
) -> None:
    # 1. Fetch cluster API endpoint and CA certificate from GKE API
    log.info("gcp_runner.gke.fetch_cluster_details", cluster=cluster_name)
    cluster_url = f"https://container.googleapis.com/v1/projects/{project_id}/locations/-/clusters/{cluster_name}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    resp = requests.get(cluster_url, headers=headers, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"GCP GKE Cluster lookup failed (HTTP {resp.status_code}): {resp.text}")
    
    cluster_data = resp.json()
    endpoint = cluster_data.get("endpoint")
    ca_cert_b64 = cluster_data.get("masterAuth", {}).get("clusterCaCertificate")

    if not endpoint or not ca_cert_b64:
        raise RuntimeError("Could not retrieve GKE cluster endpoint or CA certificate")

    # 2. Write CA cert to temp file for TLS verification in requests
    ca_cert = base64.b64decode(ca_cert_b64)
    with tempfile.NamedTemporaryFile(delete=False) as fp:
        fp.write(ca_cert)
        ca_cert_path = fp.name

    try:
        k8s_base_url = f"https://{endpoint}/apis/apps/v1/namespaces/{namespace}/deployments/{workload_name}"
        k8s_headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        if action == "GCP-RolloutRestartGKEWorkload":
            _k8s_rest.rollout_restart(
                base_url=k8s_base_url,
                headers=k8s_headers,
                ca_cert_path=ca_cert_path,
                workload=workload_name,
                log=log,
                log_prefix="gcp_runner.gke",
            )

        elif action == "GCP-ScaleGKEWorkload":
            _k8s_rest.scale_up(
                base_url=k8s_base_url,
                headers=k8s_headers,
                ca_cert_path=ca_cert_path,
                workload=workload_name,
                log=log,
                log_prefix="gcp_runner.gke",
            )

        elif action == "GCP-RollbackGKEWorkload":
            # For rollback: patch container image to rollback target if provided
            rollback_version = params.get("RollbackVersion", [""])[0]
            if not rollback_version:
                # Retrieve current image and fall back to staging/stable version
                k8s_resp = requests.get(k8s_base_url, headers=k8s_headers, verify=ca_cert_path, timeout=15)
                if k8s_resp.status_code == 200:
                    containers = k8s_resp.json().get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
                    if containers:
                        current_image = containers[0].get("image", "")
                        if ":" in current_image:
                            base_img = current_image.split(":")[0]
                            rollback_version = f"{base_img}:previous"
            
            if not rollback_version:
                raise ValueError("Could not determine rollback version for GKE workload")

            log.info("gcp_runner.gke.rollback", workload=workload_name, target_image=rollback_version)
            patch_headers = {**k8s_headers, "Content-Type": "application/strategic-merge-patch+json"}
            
            # Retrieve deployment spec to update container image
            k8s_resp = requests.get(k8s_base_url, headers=k8s_headers, verify=ca_cert_path, timeout=15)
            if k8s_resp.status_code != 200:
                raise RuntimeError(f"Failed to fetch deployment for rollback: {k8s_resp.text}")
            
            containers = k8s_resp.json().get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
            if not containers:
                raise RuntimeError("No containers found in GKE deployment spec")
            
            # Update image of the first container
            containers_patch = [{"name": containers[0]["name"], "image": rollback_version}]
            patch_body = {
                "spec": {
                    "template": {
                        "spec": {
                            "containers": containers_patch
                        }
                    }
                }
            }
            
            k8s_resp = requests.patch(k8s_base_url, headers=patch_headers, json=patch_body, verify=ca_cert_path, timeout=15)
            if k8s_resp.status_code != 200:
                raise RuntimeError(f"K8s rollback failed (HTTP {k8s_resp.status_code}): {k8s_resp.text}")
            log.info("gcp_runner.gke.rollback.success", workload=workload_name)

    finally:
        # Clean up temp CA certificate file
        try:
            os.unlink(ca_cert_path)
        except Exception:
            pass


def _run_cloudrun_action(action: str, params: dict[str, list[str]], token: str, log: Any) -> None:
    project_id = params.get("ProjectId", [""])[0]
    region = params.get("Region", ["us-central1"])[0]
    service_name = params.get("ServiceName", [""])[0]

    if not project_id or not service_name:
        raise ValueError(f"Missing Cloud Run parameters: ProjectId and ServiceName are required. Params: {params}")

    try:
        _execute_cloudrun_call(action, project_id, region, service_name, params, token, log)
    except Exception as exc:
        # Failover region detection
        failover_region = os.getenv("GCP_FAILOVER_REGION") or "us-central1"
        if failover_region == region:
            failover_region = "us-east1" if region == "us-central1" else "us-central1"

        log.warning(
            "gcp_runner.cloudrun.primary_failed.retry_failover",
            primary_region=region,
            failover_region=failover_region,
            error=str(exc)
        )
        _execute_cloudrun_call(action, project_id, failover_region, service_name, params, token, log)


def _execute_cloudrun_call(
    action: str, project_id: str, region: str, service_name: str,
    params: dict[str, list[str]], token: str, log: Any
) -> None:
    url = f"https://{region}-run.googleapis.com/v2/projects/{project_id}/locations/{region}/services/{service_name}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    if action == "GCP-ScaleCloudRunService":
        log.info("gcp_runner.cloudrun.scale", service=service_name, region=region)
        # Fetch current Cloud Run service to get concurrency details
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to fetch Cloud Run service: {resp.text}")
        
        service_data = resp.json()
        scaling = service_data.get("template", {}).get("scaling", {})
        current_max = scaling.get("maxInstanceCount", 10)
        target_max = current_max + 5
        log.info("gcp_runner.cloudrun.scale.target", current=current_max, target=target_max)

        # Update scaling properties via patch request
        patch_url = f"{url}?updateMask=template.scaling.maxInstanceCount"
        patch_body = {
            "template": {
                "scaling": {
                    "maxInstanceCount": target_max
                }
            }
        }
        
        resp = requests.patch(patch_url, headers=headers, json=patch_body, timeout=10)
        if resp.status_code != 200:
            raise RuntimeError(f"Cloud Run scale failed (HTTP {resp.status_code}): {resp.text}")
        log.info("gcp_runner.cloudrun.scale.success", service=service_name)

    elif action == "GCP-RollbackCloudRunRevision":
        # Rollback Cloud Run Service: direct traffic 100% to a specific past revision
        rollback_revision = params.get("RollbackRevision", [""])[0]
        if not rollback_revision:
            # Look up past revisions and select second-latest
            revisions_url = f"https://{region}-run.googleapis.com/v2/projects/{project_id}/locations/{region}/services/{service_name}/revisions"
            rev_resp = requests.get(revisions_url, headers=headers, timeout=10)
            if rev_resp.status_code == 200:
                revisions = rev_resp.json().get("revisions", [])
                if len(revisions) >= 2:
                    # Sort by creation time desc and take the second revision
                    revisions.sort(key=lambda r: r.get("createTime", ""), reverse=True)
                    rollback_revision = revisions[1].get("name", "")
        
        if not rollback_revision:
            raise ValueError("Could not determine rollback revision for Cloud Run service")
            
        # Extract revision name from resource path (if full path returned)
        rev_id = rollback_revision.split("/")[-1]
        log.info("gcp_runner.cloudrun.rollback", service=service_name, target_revision=rev_id, region=region)

        # Update service traffic routing block
        patch_url = f"{url}?updateMask=traffic"
        patch_body = {
            "traffic": [
                {
                    "type": "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION",
                    "revision": rev_id,
                    "percent": 100
                }
            ]
        }
        
        resp = requests.patch(patch_url, headers=headers, json=patch_body, timeout=10)
        if resp.status_code != 200:
            raise RuntimeError(f"Cloud Run rollback failed (HTTP {resp.status_code}): {resp.text}")
        log.info("gcp_runner.cloudrun.rollback.success", service=service_name)

