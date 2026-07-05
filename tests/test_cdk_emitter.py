"""
Tests for CDK TypeScript artifact emission.
"""

from __future__ import annotations

from src.agents.provisioning.cdk_emitter import build_cdk_artifact


def test_builds_lambda_cdk_artifact():
    blueprint = {
        "service_name": "image-resizer",
        "stack_name": "ImageResizerServiceStack",
        "platform": "lambda",
        "network": {"exposure": "public", "port": 443, "health_check_path": "/"},
        "capacity": {"desired_count": 1, "cpu": 256, "memory": 512},
        "integrations": ["cloudwatch", "s3_read"],
        "environments": ["dev", "prod"],
        "resources": {"reserved_concurrency": 10, "function_url": True},
        "guardrails": ["least_privilege_iam", "cloudwatch_dashboard"],
    }
    iam_plan = {
        "role_name": "image-resizer-service-role",
        "inline_statements": [
            {
                "sid": "S3ReadAccess",
                "actions": ["s3:GetObject"],
                "resources": ["arn:aws:s3:::example-bucket/*"],
            }
        ],
        "notes": ["Replace example ARNs."],
    }

    artifact = build_cdk_artifact(blueprint, iam_plan)

    assert artifact["stack_name"] == "ImageResizerServiceStack"
    paths = {file["path"] for file in artifact["files"]}
    assert "bin/app.ts" in paths
    assert "lib/image_resizer_service_stack.ts" in paths

    stack_source = next(file["content"] for file in artifact["files"] if file["path"] == "lib/image_resizer_service_stack.ts")
    assert "new lambda.Function" in stack_source
    assert "image-resizer" in stack_source


def test_builds_eks_cdk_artifact_with_descriptor():
    blueprint = {
        "service_name": "orders-api",
        "stack_name": "OrdersApiServiceStack",
        "platform": "eks",
        "network": {"exposure": "internal", "port": 8080, "health_check_path": "/healthz"},
        "capacity": {"desired_count": 2, "cpu": 512, "memory": 1024},
        "integrations": ["cloudwatch", "dynamodb_rw"],
        "environments": ["dev", "prod"],
        "resources": {"compute": "fargate_profile"},
        "guardrails": ["least_privilege_iam", "cloudwatch_dashboard"],
    }
    iam_plan = {
        "role_name": "orders-api-service-role",
        "inline_statements": [],
        "notes": [],
    }

    artifact = build_cdk_artifact(blueprint, iam_plan)

    stack_source = next(file["content"] for file in artifact["files"] if file["path"] == "lib/orders_api_service_stack.ts")
    assert "EksWorkloadDescriptor" in stack_source
    assert "desiredCount: 2" in stack_source
