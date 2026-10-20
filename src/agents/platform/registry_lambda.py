"""IAM Invoke entry point for stored preview, preparation and status observation.

IAM authenticates the calling server; that server supplies the session subject
and optional operation (omission retains the preview request shape). No Function
URL or browser entry exists. A claim is never a publication success.
"""
from datetime import datetime, timezone
import os
from uuid import uuid4

from src.agents.platform.registry_preview_service import handle_stored_event
from src.agents.platform.registry_plan_store import DynamoPlanStore
from src.agents.platform.registry_readers import DynamoCurrentUsers, GitHubSnapshotReader


def production_dependencies():
    # Lazy SDK import: module import cannot discover credentials or contact AWS.
    # No endpoint override, request-supplied table or automatic SDK write retry.
    import boto3
    from botocore.config import Config
    users_name = os.environ['REGISTRY_USERS_TABLE']
    plans_name = os.environ['REGISTRY_PLANS_TABLE']
    if not users_name or not plans_name or users_name == plans_name:
        raise ValueError('separate_plan_table_required')
    resource = boto3.resource('dynamodb', config=Config(
        connect_timeout=3, read_timeout=5, retries={'total_max_attempts': 1},
        ignore_configured_endpoint_urls=True,
    ))
    return (DynamoCurrentUsers(resource.Table(users_name)), GitHubSnapshotReader(
        os.environ['REGISTRY_REPOSITORY'], os.environ['REGISTRY_BRANCH'],
    ), DynamoPlanStore(resource.Table(plans_name)))


def handle_event(event, *, dependencies_factory, request_id: str, clock):
    if (not isinstance(event, dict) or set(event) not in (
            {'subject', 'request'}, {'operation', 'subject', 'request'})):
        return dict(ok=False, status=422, error='invalid_invoke_request')
    operation = event.get('operation', 'preview')
    if not isinstance(operation, str) or operation not in ('preview', 'prepare', 'status'):
        return dict(ok=False, status=422, error='invalid_invoke_request')
    return handle_stored_event(
        {'subject': event['subject'], 'request': event['request']}, operation=operation,
        dependencies_factory=dependencies_factory, request_id=request_id, clock=clock,
    )


def handler(event, context):
    return handle_event(
        event, dependencies_factory=production_dependencies,
        request_id=getattr(context, 'aws_request_id', None) or str(uuid4()),
        clock=lambda: datetime.now(timezone.utc),
    )
