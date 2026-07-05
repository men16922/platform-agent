"""
Tests for runtime router ingress handler.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest


class TestRouterHandler:
    @patch("src.agents.router.handler._SFN")
    @patch("src.agents.router.handler._PROVISIONING_STATE_MACHINE_ARN", "arn:aws:states:ap-northeast-2:123456789012:stateMachine:platform-agent-provisioning")
    def test_routes_provisioning_request(self, mock_sfn):
        from src.agents.router.handler import lambda_handler

        mock_sfn.start_execution.return_value = {
            "executionArn": "arn:aws:states:ap-northeast-2:123456789012:execution:platform-agent-provisioning:exec-1"
        }

        event = {
            "id": "evt-123",
            "source": "platform-agent",
            "detail-type": "Provisioning Request",
            "detail": {
                "service_name": "orders-api",
                "platform": "eks",
                "requester": "eng-alice",
            },
        }

        result = lambda_handler(event, None)

        assert result["route"] == "provisioning"
        kwargs = mock_sfn.start_execution.call_args.kwargs
        assert kwargs["stateMachineArn"].endswith("platform-agent-provisioning")
        assert json.loads(kwargs["input"])["service_name"] == "orders-api"
        assert kwargs["name"].startswith("provisioning-")

    @patch("src.agents.router.handler._SFN")
    @patch("src.agents.router.handler._DEPLOYMENT_STATE_MACHINE_ARN", "arn:aws:states:ap-northeast-2:123456789012:stateMachine:platform-agent-deployment")
    def test_routes_deployment_request_from_pipeline_hint(self, mock_sfn):
        from src.agents.router.handler import lambda_handler

        mock_sfn.start_execution.return_value = {
            "executionArn": "arn:aws:states:ap-northeast-2:123456789012:execution:platform-agent-deployment:exec-2"
        }

        event = {
            "id": "evt-456",
            "source": "platform-agent.github",
            "detail-type": "Custom Request",
            "detail": {
                "pipeline": "deployment_validation",
                "deployment_id": "deploy-123",
                "service_name": "orders-api",
                "version": "v1.2.3",
            },
        }

        result = lambda_handler(event, None)

        assert result["route"] == "deployment"
        kwargs = mock_sfn.start_execution.call_args.kwargs
        assert kwargs["stateMachineArn"].endswith("platform-agent-deployment")
        assert json.loads(kwargs["input"])["deployment_id"] == "deploy-123"
        assert kwargs["name"] == "deployment-deploy-123"

    def test_rejects_unsupported_event(self):
        from src.agents.router.handler import lambda_handler

        event = {
            "source": "platform-agent",
            "detail-type": "Unknown Request",
            "detail": {"foo": "bar"},
        }

        with pytest.raises(ValueError):
            lambda_handler(event, None)
