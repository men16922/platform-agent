"""
Tests for provisioning artifact persistence.
"""

import io
import zipfile
from unittest.mock import MagicMock, patch


@patch("src.agents.provisioning.artifact_writer._ARTIFACT_BUCKET", "artifact-bucket")
@patch("src.agents.provisioning.artifact_writer._ARTIFACT_PREFIX", "plans")
@patch("src.agents.provisioning.artifact_writer._DYNAMO")
@patch("src.agents.provisioning.artifact_writer._S3")
def test_writes_cdk_artifact_bundle_and_updates_plan(mock_s3, mock_dynamo):
    from src.agents.provisioning.artifact_writer import lambda_handler

    mock_table = MagicMock()
    mock_dynamo.Table.return_value = mock_table

    event = {
        "plan_id": "PLAN-1234ABCD",
        "requester": "eng-alice",
        "blueprint": {
            "service_name": "orders-api",
            "platform": "eks",
        },
        "cdk_artifact": {
            "files": [
                {"path": "bin/app.ts", "content": "console.log('hello');\n"},
                {"path": "manifest.json", "content": '{"service":"orders-api"}\n'},
            ]
        },
    }

    result = lambda_handler(event, None)

    put_kwargs = mock_s3.put_object.call_args.kwargs
    assert put_kwargs["Bucket"] == "artifact-bucket"
    assert put_kwargs["Key"] == "plans/PLAN-1234ABCD/orders-api-cdk-artifact.zip"
    assert put_kwargs["ContentType"] == "application/zip"

    archive = zipfile.ZipFile(io.BytesIO(put_kwargs["Body"]))
    assert set(archive.namelist()) == {"bin/app.ts", "manifest.json"}
    assert archive.read("bin/app.ts").decode("utf-8") == "console.log('hello');\n"

    mock_table.update_item.assert_called_once()
    update_kwargs = mock_table.update_item.call_args.kwargs
    assert update_kwargs["Key"] == {"plan_id": "PLAN-1234ABCD"}
    assert update_kwargs["ExpressionAttributeValues"][":status"] == "artifact_ready"
    assert update_kwargs["ExpressionAttributeValues"][":uri"] == (
        "s3://artifact-bucket/plans/PLAN-1234ABCD/orders-api-cdk-artifact.zip"
    )

    assert result["status"] == "artifact_ready"
    assert result["artifact_bundle"]["file_count"] == 2
    assert result["artifact_bundle"]["s3_uri"] == (
        "s3://artifact-bucket/plans/PLAN-1234ABCD/orders-api-cdk-artifact.zip"
    )
