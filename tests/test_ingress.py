"""
Tests for generic ingress handler.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest


class TestIngressHandler:
    @patch("src.agents.ingress.handler._EVENTS")
    def test_http_provisioning_request_publishes_eventbridge_event(self, mock_events):
        from src.agents.ingress.handler import lambda_handler

        mock_events.put_events.return_value = {
            "FailedEntryCount": 0,
            "Entries": [{"EventId": "evt-1"}],
        }

        event = {
            "requestContext": {"http": {"method": "POST", "path": "/"}},
            "body": json.dumps(
                {
                    "pipeline": "provisioning",
                    "detail": {
                        "service_name": "orders-api",
                        "platform": "eks",
                    },
                }
            ),
            "isBase64Encoded": False,
        }

        result = lambda_handler(event, None)

        assert result["statusCode"] == 202
        body = json.loads(result["body"])
        assert body["detail_type"] == "Provisioning Request"
        kwargs = mock_events.put_events.call_args.kwargs
        assert kwargs["Entries"][0]["Source"] == "platform-agent.api"
        assert json.loads(kwargs["Entries"][0]["Detail"])["service_name"] == "orders-api"

    @patch("src.agents.ingress.handler._EVENTS")
    def test_direct_deployment_request_keeps_detail_type(self, mock_events):
        from src.agents.ingress.handler import lambda_handler

        mock_events.put_events.return_value = {
            "FailedEntryCount": 0,
            "Entries": [{"EventId": "evt-2"}],
        }

        event = {
            "source": "platform-agent.github",
            "detail-type": "Deployment Validation Request",
            "detail": {
                "deployment_id": "deploy-123",
                "service_name": "orders-api",
                "version": "v1.2.3",
            },
        }

        result = lambda_handler(event, None)

        assert result["accepted"] is True
        assert result["detail_type"] == "Deployment Validation Request"
        kwargs = mock_events.put_events.call_args.kwargs
        assert kwargs["Entries"][0]["Source"] == "platform-agent.github"

    def test_rejects_unknown_pipeline_without_detail_type(self):
        from src.agents.ingress.handler import lambda_handler

        with pytest.raises(ValueError):
            lambda_handler({"pipeline": "unknown", "service_name": "orders-api"}, None)
