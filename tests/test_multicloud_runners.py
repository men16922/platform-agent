"""
Unit and integration tests for multi-cloud runners and authentication.
"""

from __future__ import annotations

import json
import os
from unittest import mock

import pytest

from src.agents.operations.executor.gcp_auth import get_gcp_access_token
from src.agents.operations.executor.gcp_runner import run_gcp_action
from src.agents.operations.executor.azure_runner import run_azure_action


class TestGcpAuth:
    @mock.patch("src.agents.operations.executor.gcp_auth._get_token_via_wif")
    def test_wif_preferred_when_env_vars_set(self, mock_wif):
        mock_wif.return_value = "mock-wif-token"
        
        env = {
            "GCP_PROJECT_NUMBER": "12345678",
            "GCP_SERVICE_ACCOUNT_EMAIL": "agent@project.iam.gserviceaccount.com",
            "GCP_WORKLOAD_POOL_ID": "pool-id",
            "GCP_WORKLOAD_PROVIDER_ID": "provider-id"
        }
        with mock.patch.dict(os.environ, env):
            token = get_gcp_access_token()
            assert token == "mock-wif-token"
            mock_wif.assert_called_once_with("12345678", "pool-id", "provider-id", "agent@project.iam.gserviceaccount.com")

    @mock.patch("src.agents.operations.executor.gcp_auth._get_token_via_sa_key")
    def test_sa_key_fallback_when_wif_missing(self, mock_sa_key):
        mock_sa_key.return_value = "mock-sa-token"
        
        env = {
            "GCP_PROJECT_NUMBER": "",
            "GCP_SERVICE_ACCOUNT_EMAIL": "",
            "GCP_SERVICE_ACCOUNT_KEY": '{"type": "service_account"}'
        }
        with mock.patch.dict(os.environ, env):
            token = get_gcp_access_token()
            assert token == "mock-sa-token"
            mock_sa_key.assert_called_once_with('{"type": "service_account"}')


class TestGcpRunner:
    def test_run_gcp_action_in_mock_mode(self):
        log = mock.Mock()
        params = {
            "ProjectId": ["gcp-proj-1"],
            "ClusterName": ["gke-cluster-1"],
            "WorkloadName": ["orders-api"],
            "Namespace": ["default"]
        }
        
        # GCP_MOCK=true forces mock mode
        with mock.patch.dict(os.environ, {"GCP_MOCK": "true"}):
            run_gcp_action("GCP-RolloutRestartGKEWorkload", params, log)
            log.info.assert_called_once_with(
                "gcp_runner.mock_execution",
                action="GCP-RolloutRestartGKEWorkload",
                params=params
            )

    @mock.patch("src.agents.operations.executor.gcp_runner.get_gcp_access_token")
    @mock.patch("requests.get")
    @mock.patch("requests.patch")
    def test_run_gke_rollout_restart_real_api_call(self, mock_patch, mock_get, mock_token):
        mock_token.return_value = "fake-gcp-token"
        log = mock.Mock()
        
        # Mock GKE cluster metadata lookup response
        mock_cluster_resp = mock.Mock()
        mock_cluster_resp.status_code = 200
        mock_cluster_resp.json.return_value = {
            "endpoint": "10.0.0.1",
            "masterAuth": {
                "clusterCaCertificate": "dGVzdC1jYS1jZXJ0"  # base64 encoded "test-ca-cert"
            }
        }
        mock_get.return_value = mock_cluster_resp
        
        # Mock K8s strategic merge patch response
        mock_patch_resp = mock.Mock()
        mock_patch_resp.status_code = 200
        mock_patch_resp.json.return_value = {"status": "Success"}
        mock_patch.return_value = mock_patch_resp

        params = {
            "ProjectId": ["gcp-proj-1"],
            "ClusterName": ["gke-cluster-1"],
            "WorkloadName": ["orders-api"],
            "Namespace": ["default"]
        }
        
        with mock.patch.dict(os.environ, {"GCP_MOCK": "false", "TESTING": "False"}):
            run_gcp_action("GCP-RolloutRestartGKEWorkload", params, log)
            
            # GKE cluster lookup assertion
            mock_get.assert_called_once_with(
                "https://container.googleapis.com/v1/projects/gcp-proj-1/locations/-/clusters/gke-cluster-1",
                headers={"Authorization": "Bearer fake-gcp-token", "Content-Type": "application/json"},
                timeout=15
            )
            
            # K8s deploy rollout patch assertion
            mock_patch.assert_called_once()
            args, kwargs = mock_patch.call_args
            assert args[0] == "https://10.0.0.1/apis/apps/v1/namespaces/default/deployments/orders-api"
            assert kwargs["headers"]["Authorization"] == "Bearer fake-gcp-token"
            assert "kubectl.kubernetes.io/restartedAt" in kwargs["json"]["spec"]["template"]["metadata"]["annotations"]


class TestAzureRunner:
    def test_run_azure_action_in_mock_mode(self):
        log = mock.Mock()
        params = {
            "ClusterId": ["/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.ContainerService/managedClusters/aks1"],
            "WorkloadName": ["orders-api"],
            "Namespace": ["default"]
        }
        
        with mock.patch.dict(os.environ, {"AZURE_MOCK": "true"}):
            run_azure_action("AZURE-RolloutRestartAKSWorkload", params, log)
            log.info.assert_called_once_with(
                "azure_runner.mock_execution",
                action="AZURE-RolloutRestartAKSWorkload",
                params=params
            )
