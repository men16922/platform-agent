"""
Azure Action Runner.

Handles Azure API calls for AKS and Function App remediations.
Supports OIDC credentials federation (Azure AD Federated Credentials) and fallback.
"""

from __future__ import annotations

import os
import time
from typing import Any

import requests
import structlog

logger = structlog.get_logger(__name__)


def run_azure_action(action: str, params: dict[str, list[str]], log: Any) -> None:
    """
    Executes a real Azure remediation action.
    Falls back to mock simulation if AZURE_MOCK=True or in testing environment without credentials.
    """
    is_mock = os.getenv("AZURE_MOCK", "false").lower() == "true" or os.getenv("TESTING") == "True"
    
    if is_mock:
        log.info("azure_runner.mock_execution", action=action, params=params)
        time.sleep(1)  # Simulate execution latency
        return

    # In production, we get access token via Federated Credentials or environment vars
    try:
        token = _get_azure_access_token()
    except Exception as e:
        log.error("azure_runner.auth_failed", error=str(e))
        raise RuntimeError(f"Azure Authentication failed: {e}")

    if action in {"AZURE-RolloutRestartAKSWorkload", "AZURE-ScaleAKSNodePool", "AZURE-RollbackAKSWorkload"}:
        _run_aks_action(action, params, token, log)
    elif action in {"AZURE-ScaleFunctionApp", "AZURE-RollbackFunctionApp"}:
        _run_functionapp_action(action, params, token, log)
    else:
        raise ValueError(f"Unsupported Azure action: {action}")


def _get_azure_access_token() -> str:
    """
    Get Azure Management Resource token using Client Credentials or Federated Identity.
    """
    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    
    if not tenant_id or not client_id:
        raise ValueError("Missing AZURE_TENANT_ID or AZURE_CLIENT_ID env variables")

    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    # Try Workload Identity Federated Credential first
    # AWS Lambda role receives AWS Web Identity token which can be exchanged with Azure AD
    aws_token = os.getenv("AWS_WEB_IDENTITY_TOKEN")
    
    if aws_token:
        # Federated credential swap
        payload = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": aws_token,
            "scope": "https://management.azure.com/.default",
        }
    else:
        # Fallback: Client secret
        client_secret = os.getenv("AZURE_CLIENT_SECRET")
        if not client_secret:
            raise ValueError("No AZURE_CLIENT_SECRET or federated AWS token found")
        payload = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://management.azure.com/.default",
        }

    resp = requests.post(url, data=payload, headers=headers, timeout=10)
    if resp.status_code != 200:
        raise RuntimeError(f"Azure AD OAuth token acquisition failed (HTTP {resp.status_code}): {resp.text}")
        
    return str(resp.json()["access_token"])


def _run_aks_action(action: str, params: dict[str, list[str]], token: str, log: Any) -> None:
    cluster_id = params.get("ClusterId", [""])[0]
    namespace = params.get("Namespace", ["default"])[0]
    workload_name = params.get("WorkloadName", [""])[0]

    if not cluster_id or not workload_name:
        raise ValueError(f"Missing AKS parameters: ClusterId and WorkloadName are required. Params: {params}")

    try:
        _execute_aks_call(action, cluster_id, namespace, workload_name, params, token, log)
    except Exception as exc:
        failover_cluster_id = os.getenv("AZURE_FAILOVER_CLUSTER_ID") or f"{cluster_id}-backup"
        log.warning(
            "azure_runner.aks.primary_failed.retry_failover",
            primary_cluster_id=cluster_id,
            failover_cluster_id=failover_cluster_id,
            error=str(exc)
        )
        _execute_aks_call(action, failover_cluster_id, namespace, workload_name, params, token, log)


def _execute_aks_call(
    action: str, cluster_id: str, namespace: str, workload_name: str,
    params: dict[str, list[str]], token: str, log: Any
) -> None:
    # 1. Retrieve AKS Cluster user credentials (kubeconfig/admin credentials) via Azure Resource Manager API
    log.info("azure_runner.aks.get_credentials", cluster_id=cluster_id)
    cred_url = f"https://management.azure.com{cluster_id}/listClusterUserCredentials?api-version=2023-11-01"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    resp = requests.post(cred_url, headers=headers, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch AKS cluster credentials (HTTP {resp.status_code}): {resp.text}")

    # We extract kubeconfig details (usually returned in a base64 encoded kubeconfigs list)
    kubeconfig_b64 = resp.json().get("kubeconfigs", [{}])[0].get("value", "")
    if not kubeconfig_b64:
        raise RuntimeError("No kubeconfig credentials returned by Azure AKS API")
    
    # We parse the API server endpoint and CA cert from the returned kubeconfig yaml
    import yaml
    kubeconfig = yaml.safe_load(base64_decode_string(kubeconfig_b64))
    
    cluster_conf = kubeconfig.get("clusters", [{}])[0].get("cluster", {})
    endpoint = cluster_conf.get("server", "").replace("https://", "")
    ca_cert_b64 = cluster_conf.get("certificate-authority-data", "")
    
    user_token = kubeconfig.get("users", [{}])[0].get("user", {}).get("token", "")
    if not user_token:
        # Use our original Azure token if user token is empty
        user_token = token

    # 2. Decode cluster CA cert
    import base64
    import tempfile
    ca_cert = base64.b64decode(ca_cert_b64)
    with tempfile.NamedTemporaryFile(delete=False) as fp:
        fp.write(ca_cert)
        ca_cert_path = fp.name

    try:
        k8s_base_url = f"https://{endpoint}/apis/apps/v1/namespaces/{namespace}/deployments/{workload_name}"
        k8s_headers = {
            "Authorization": f"Bearer {user_token}",
            "Accept": "application/json",
        }

        if action == "AZURE-RolloutRestartAKSWorkload":
            log.info("azure_runner.aks.rollout_restart", workload=workload_name)
            # Patch deployment annotations to trigger rollout restart
            patch_headers = {**k8s_headers, "Content-Type": "application/strategic-merge-patch+json"}
            patch_body = {
                "spec": {
                    "template": {
                        "metadata": {
                            "annotations": {
                                "kubectl.kubernetes.io/restartedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                            }
                        }
                    }
                }
            }
            k8s_resp = requests.patch(k8s_base_url, headers=patch_headers, json=patch_body, verify=ca_cert_path, timeout=15)
            if k8s_resp.status_code != 200:
                raise RuntimeError(f"K8s rollout restart failed (HTTP {k8s_resp.status_code}): {k8s_resp.text}")
            log.info("azure_runner.aks.rollout_restart.success", workload=workload_name)

        elif action == "AZURE-ScaleAKSNodePool":
            # Scale workload replicas in AKS
            log.info("azure_runner.aks.scale", workload=workload_name)
            k8s_resp = requests.get(k8s_base_url, headers=k8s_headers, verify=ca_cert_path, timeout=15)
            if k8s_resp.status_code != 200:
                raise RuntimeError(f"Failed to fetch deployment details: {k8s_resp.text}")
            
            deployment = k8s_resp.json()
            current_replicas = deployment.get("spec", {}).get("replicas", 1)
            target_replicas = current_replicas + 1
            log.info("azure_runner.aks.scale.target", current=current_replicas, target=target_replicas)

            patch_headers = {**k8s_headers, "Content-Type": "application/merge-patch+json"}
            patch_body = {"spec": {"replicas": target_replicas}}
            
            k8s_resp = requests.patch(k8s_base_url, headers=patch_headers, json=patch_body, verify=ca_cert_path, timeout=15)
            if k8s_resp.status_code != 200:
                raise RuntimeError(f"K8s scale failed (HTTP {k8s_resp.status_code}): {k8s_resp.text}")
            log.info("azure_runner.aks.scale.success", workload=workload_name, replicas=target_replicas)

        elif action == "AZURE-RollbackAKSWorkload":
            rollback_version = params.get("RollbackVersion", [""])[0]
            if not rollback_version:
                raise ValueError("RollbackVersion parameter is required for AKS rollback")

            log.info("azure_runner.aks.rollback", workload=workload_name, version=rollback_version)
            patch_headers = {**k8s_headers, "Content-Type": "application/strategic-merge-patch+json"}
            
            # Fetch current containers to identify first container name
            k8s_resp = requests.get(k8s_base_url, headers=k8s_headers, verify=ca_cert_path, timeout=15)
            if k8s_resp.status_code != 200:
                raise RuntimeError(f"Failed to fetch deployment: {k8s_resp.text}")
            
            containers = k8s_resp.json().get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
            if not containers:
                raise RuntimeError("No containers found in deployment spec")
                
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
            log.info("azure_runner.aks.rollback.success", workload=workload_name)

    finally:
        try:
            os.unlink(ca_cert_path)
        except Exception:
            pass


def _run_functionapp_action(action: str, params: dict[str, list[str]], token: str, log: Any) -> None:
    resource_id = params.get("ResourceId", [""])[0]
    app_name = params.get("FunctionAppName", [""])[0]

    if not resource_id:
        raise ValueError(f"Missing ResourceId for Azure Function App. Params: {params}")

    try:
        _execute_functionapp_call(action, resource_id, app_name, params, token, log)
    except Exception as exc:
        failover_resource_id = os.getenv("AZURE_FAILOVER_RESOURCE_ID") or f"{resource_id}-backup"
        failover_app_name = f"{app_name}-backup"
        log.warning(
            "azure_runner.functionapp.primary_failed.retry_failover",
            primary_resource_id=resource_id,
            failover_resource_id=failover_resource_id,
            error=str(exc)
        )
        _execute_functionapp_call(action, failover_resource_id, failover_app_name, params, token, log)


def _execute_functionapp_call(
    action: str, resource_id: str, app_name: str,
    params: dict[str, list[str]], token: str, log: Any
) -> None:
    url = f"https://management.azure.com{resource_id}?api-version=2022-03-01"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    if action == "AZURE-ScaleFunctionApp":
        log.info("azure_runner.functionapp.scale", app=app_name)
        # In Azure, scaling function app concurrency can be managed by setting HTTPS limits or scale-out properties
        # For simplicity, we trigger a restart or update app properties
        # Let's perform a post request to trigger app restart to clear load spikes:
        restart_url = f"https://management.azure.com{resource_id}/restart?api-version=2022-03-01"
        resp = requests.post(restart_url, headers=headers, timeout=15)
        if resp.status_code not in {200, 204}:
            raise RuntimeError(f"Azure Function App restart/scale failed (HTTP {resp.status_code}): {resp.text}")
        log.info("azure_runner.functionapp.scale.success", app=app_name)

    elif action == "AZURE-RollbackFunctionApp":
        # Rollback app code: trigger slot swap or rollback app version configuration
        log.info("azure_runner.functionapp.rollback", app=app_name)
        # To rollback, we can perform a slot swap from staging to production:
        swap_url = f"https://management.azure.com{resource_id}/slotswap?api-version=2022-03-01"
        # We target staging slot rollback
        payload = {
            "targetSlot": "staging",
            "preserveVnet": True
        }
        resp = requests.post(swap_url, headers=headers, json=payload, timeout=15)
        if resp.status_code not in {200, 202, 204}:
            raise RuntimeError(f"Azure Function App slotswap rollback failed (HTTP {resp.status_code}): {resp.text}")
        log.info("azure_runner.functionapp.rollback.success", app=app_name)


def base64_decode_string(s: str) -> str:
    import base64
    return base64.b64decode(s).decode("utf-8")

