"""Server-held previews and a single conditional claim; no GitHub write client.

The table and authenticated subject are trusted server dependencies. The Lambda
and explicit local service share this contract. CLAIMED never returns
to PREVIEW automatically: an interrupted caller must reconcile before publishing.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from uuid import uuid4

from src.agents.platform.registry_authorization import authorize_attachment_request
from src.agents.platform.registry_planner import (
    CONTRACT_VERSION, MAX_FILE_BYTES, PlanEnvelope, PlannerError,
    validate_attachment_request,
)


def _clock(now):
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise PlannerError('invalid_server_context')
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = now.astimezone(timezone.utc) - epoch
    return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value):
        raise PlannerError('invalid_request')
    return value


@dataclass(frozen=True)
class StoredPreview:
    request_id: str
    subject: str
    payload: str
    expires_us: int

    def data(self):
        return json.loads(self.payload)  # fresh copy; callers cannot mutate storage


def stored_preview(plan: PlanEnvelope, *, subject: str, request: dict,
                   output: str, now: datetime) -> StoredPreview:
    """Bind trusted planner output to the existing public envelope digest."""
    now_us = _clock(now)
    if not isinstance(plan, PlanEnvelope):
        raise PlannerError('invalid_stored_plan')
    _id(plan.request_id)
    request = validate_attachment_request(request)
    if (not isinstance(subject, str) or not subject or subject != subject.strip()
            or subject != subject.lower() or len(subject) > 256
            or any(ord(c) < 32 or ord(c) == 127 for c in subject)):
        raise PlannerError('invalid_stored_plan')
    envelope = plan.to_dict()
    public = {k: v for k, v in envelope.items() if k != 'digest'}
    digest = hashlib.sha256(json.dumps(
        {**public, 'subject': subject, 'request': request}, sort_keys=True,
        separators=(',', ':'), ensure_ascii=True,
    ).encode()).hexdigest()
    try:
        expires_us = _clock(datetime.fromisoformat(plan.expires_at))
        output_bytes = output.encode('utf-8')
    except (ValueError, TypeError, AttributeError):
        raise PlannerError('invalid_stored_plan') from None
    if (plan.contract_version != CONTRACT_VERSION or plan.digest != digest
            or plan.path != f"platform/tenants/{request['tenant']}.yaml"
            or not isinstance(output, str) or len(output_bytes) > MAX_FILE_BYTES
            or hashlib.sha256(output_bytes).hexdigest() != plan.output_sha256
            or not now_us < expires_us <= now_us + 300_000_000):
        raise PlannerError('invalid_stored_plan')
    payload = json.dumps({'subject': subject, 'request': request, 'plan': envelope,
                          'output': output}, sort_keys=True, ensure_ascii=False)
    # Leave headroom beneath DynamoDB's item limit for names and claim metadata.
    if len(payload.encode('utf-8')) > 350 * 1024:
        raise PlannerError('stored_plan_too_large')
    return StoredPreview(plan.request_id, subject, payload, expires_us)


class DynamoPlanStore:
    """Injected boto3 Table; request_id is the partition key, no global client."""
    def __init__(self, table):
        self.table = table

    def _call(self, operation, **kwargs):
        try:
            return getattr(self.table, operation)(**kwargs)
        except Exception as error:
            code = getattr(error, 'response', {}).get('Error', {}).get('Code')
            if code == 'ConditionalCheckFailedException':
                raise PlannerError('plan_conflict', 409) from None
            raise PlannerError('plan_store_unavailable', 503) from None

    def put(self, preview: StoredPreview):
        self._call('put_item', Item={
            'request_id': preview.request_id, 'subject': preview.subject,
            'payload': preview.payload, 'expires_us': preview.expires_us,
            'ttl': preview.expires_us // 1_000_000, 'state': 'PREVIEW',
        }, ConditionExpression='attribute_not_exists(request_id)')

    def get(self, request_id: str):
        return self._call('get_item', Key={'request_id': _id(request_id)},
                          ConsistentRead=True).get('Item')

    def claim(self, row: dict, *, now: datetime):
        claim_id = uuid4().hex
        self._call('update_item', Key={'request_id': row['request_id']},
                   UpdateExpression='SET #state = :claimed, claim_id = :claim REMOVE #ttl',
                   ConditionExpression='#state = :preview AND payload = :payload '
                                       'AND subject = :subject AND expires_us = :expires AND expires_us > :now',
                   ExpressionAttributeNames={'#state': 'state', '#ttl': 'ttl'},
                   ExpressionAttributeValues={':claimed': 'CLAIMED', ':preview': 'PREVIEW',
                       ':claim': claim_id, ':payload': row['payload'],
                       ':subject': row['subject'], ':expires': row['expires_us'], ':now': _clock(now)})
        return claim_id


def claim_stored_preview(request_id: str, *, subject: str | None,
                         store: DynamoPlanStore, users, reader, clock):
    """Only request_id comes from the submit body; diff/tenant/path are server-held.

    Returns a claim receipt and trusted payload, not a publication success. No
    lease expiry or retry can reopen the record. Reauthorization and GitHub reads
    are not atomic with DynamoDB; a future writer must check its own preconditions.
    """
    now = clock()
    now_us = _clock(now)
    if not isinstance(subject, str) or not subject:
        raise PlannerError('session_required', 401)
    row = store.get(request_id)
    if row is None or row.get('subject') != subject.lower():
        raise PlannerError('stored_plan_not_found', 404)
    try:
        data = json.loads(row['payload'])
        plan = PlanEnvelope(**data['plan'])
        if int(row['expires_us']) <= now_us:
            raise PlannerError('plan_expired', 409)
        # Revalidate server storage corruption without extending its original TTL.
        check = stored_preview(plan, subject=data['subject'], request=data['request'],
                               output=data['output'], now=now)
        if (check.request_id != request_id or check.subject != row['subject']
                or check.expires_us != row['expires_us'] or check.payload != row['payload']):
            raise PlannerError('invalid_stored_plan')
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, PlannerError) and error.code == 'plan_expired':
            raise
        raise PlannerError('invalid_stored_plan', 503) from None
    authorize_attachment_request(data['request'], subject=subject, users=users)
    if row.get('state') != 'PREVIEW':
        raise PlannerError('plan_conflict', 409)
    try:
        revision = reader.resolve_revision()
    except Exception:
        raise PlannerError('snapshot_unavailable', 503) from None
    if revision != plan.base_commit:
        raise PlannerError('snapshot_revision_mismatch', 409)
    claim_id = store.claim(row, now=clock())
    return {'request_id': request_id, 'claim_id': claim_id, 'state': 'CLAIMED',
            'payload': data}


def _status_record(row, *, request_id, subject, now):
    """Validate retained records without extending expiry or exposing their payload."""
    if row is None or row.get('subject') != subject.lower():
        raise PlannerError('stored_plan_not_found', 404)
    try:
        data = json.loads(row['payload'])
        plan = PlanEnvelope(**data['plan'])
        expiry = datetime.fromisoformat(plan.expires_at)
        now_us = _clock(now)
        # Expired PREVIEW and retained CLAIMED remain readable. This reference
        # time validates only the immutable artifact; it cannot authorize claim.
        reference_time = min(now, expiry - timedelta(microseconds=1))
        check = stored_preview(plan, subject=data['subject'], request=data['request'],
                               output=data['output'], now=reference_time)
        if (check.request_id != request_id or row['request_id'] != request_id
                or check.subject != row['subject'] or check.expires_us != row['expires_us']
                or check.payload != row['payload']):
            raise ValueError('record_mismatch')
        state = row.get('state')
        if state == 'PREVIEW':
            if 'claim_id' in row or row.get('ttl') != check.expires_us // 1_000_000:
                raise ValueError('preview_state_mismatch')
        elif state == 'CLAIMED':
            if ('ttl' in row or not isinstance(row.get('claim_id'), str)
                    or re.fullmatch(r'[a-f0-9]{32}', row['claim_id']) is None):
                raise ValueError('claim_state_mismatch')
        else:
            raise ValueError('unknown_state')
        return {'request_id': request_id, 'state': state, 'published': False,
                'expires_at': plan.expires_at, 'expired': now_us >= check.expires_us}, data
    except (KeyError, TypeError, ValueError, AttributeError):
        raise PlannerError('invalid_stored_plan', 503) from None


def read_stored_status(request_id, *, subject, store, users, clock):
    """Observe own current state; no claim, GitHub read, or publication authority.

    Authorization and storage are not atomic. Re-read after authorization to see
    a concurrent claim; immutable changes or a reopened claim are rejected.
    """
    _id(request_id)
    if not isinstance(subject, str) or not subject:
        raise PlannerError('session_required', 401)
    row = store.get(request_id)
    _, data = _status_record(row, request_id=request_id, subject=subject, now=clock())
    authorize_attachment_request(data['request'], subject=subject, users=users)
    current = store.get(request_id)
    status, current_data = _status_record(current, request_id=request_id, subject=subject, now=clock())
    if (current_data != data or (row['state'] == 'CLAIMED'
            and (current['state'] != 'CLAIMED' or current.get('claim_id') != row.get('claim_id')))):
        raise PlannerError('plan_changed_during_read', 409)
    return status
