"""Stored preview and preparation service. No publication adapter or AWS globals.

Both local and IAM Lambda transports use the same stored contract. Production
requires a separate plan table; no publication adapter is wired here.
"""
from datetime import datetime

from src.agents.platform.registry_authorization import authorize_attachment_request
from src.agents.platform.registry_plan_store import _id, claim_stored_preview, read_stored_status, stored_preview
from src.agents.platform.registry_planner import (
    PlannerError, plan_snapshot_artifact, validate_attachment_request,
)


def handle_stored_event(event, *, operation, dependencies_factory, request_id, clock):
    """Operation and subject are supplied by the trusted transport, not the body.

    PREVIEW is returned only after persistence; a lost response never reopens a
    claimed record. Preparation receipts omit the internal output and claim_id.
    """
    try:
        if (operation not in ('preview', 'prepare', 'status') or not isinstance(event, dict)
                or set(event) != {'subject', 'request'}):
            raise PlannerError('invalid_request')
        subject = event['subject']
        if (not isinstance(subject, str) or not subject or len(subject) > 256
                or subject != subject.strip()
                or any(ord(c) < 32 or ord(c) == 127 for c in subject)):
            raise PlannerError('session_required', 401)
        request = event['request']
        if operation in ('prepare', 'status'):
            if (not isinstance(request, dict) or set(request) != {'request_id'}):
                raise PlannerError('invalid_request')
            _id(request['request_id'])
        else:
            request = validate_attachment_request(request)
        users, reader, store = dependencies_factory()
        if operation == 'status':
            return dict(ok=True, status=200, observation=read_stored_status(
                request['request_id'], subject=subject, store=store, users=users, clock=clock))
        if operation == 'prepare':
            claim = claim_stored_preview(request['request_id'], subject=subject,
                store=store, users=users, reader=reader, clock=clock)
            return dict(ok=True, status=200, preparation={
                'request_id': claim['request_id'], 'state': claim['state'], 'published': False})
        username, values = authorize_attachment_request(request, subject=subject, users=users)
        artifact = plan_snapshot_artifact(values, subject=username, reader=reader,
                                          request_id=request_id, now=clock())
        # Recheck time after planning. A slow read must not produce an expired preview.
        now = clock()
        if datetime.fromisoformat(artifact.envelope.expires_at) <= now:
            raise PlannerError('plan_expired', 409)
        record = stored_preview(artifact.envelope, subject=username, request=values,
                                output=artifact.output, now=now)
        store.put(record)
        # Persistence may also take the preview beyond its deadline; retain the row,
        # but do not acknowledge a usable preview after expiry.
        if datetime.fromisoformat(artifact.envelope.expires_at) <= clock():
            raise PlannerError('plan_expired', 409)
        return dict(ok=True, status=200, plan=artifact.envelope.to_dict())
    except PlannerError as error:
        return dict(ok=False, status=error.status, error=error.code)
    except Exception:
        return dict(ok=False, status=503, error='planner_unavailable')
