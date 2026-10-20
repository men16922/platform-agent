"""Opt-in operator PR-error excerpts, separate from the fixed M73 evidence contract.

Only use for reviewed synthetic experiments. Known credentials and common secret
shapes are redacted; this is not a general DLP guarantee for arbitrary response
text. Excerpts remain untrusted and must never authorize a write or a retry.
"""
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import unicodedata
from urllib.parse import quote, quote_plus
from uuid import uuid4

from src.agents.platform.writer_attempt import _directory, _write_new
from src.agents.platform.writer_capture import MAX_ERRORS, MAX_RECORD, _message, _request_id

MAX_DETAIL_BYTES = 1024
MAX_MESSAGE_BYTES = 512


def _normalize(value):
    value = unicodedata.normalize('NFKC', value)
    return ''.join(c if c in '\n\r\t' or not unicodedata.category(c).startswith('C') else '' for c in value)


class ErrorDetailJournal:
    """Explicit private directory and three supplied identities; no credential discovery."""
    def __init__(self, directory, *, secrets):
        if (not isinstance(secrets, (tuple, list)) or len(secrets) != 3
                or any(not isinstance(s, str) or not 1 <= len(s) <= 8192 for s in secrets)):
            raise ValueError('invalid_diagnostic_secrets')
        self.directory = Path(directory)
        fd = _directory(self.directory)
        os.close(fd)
        forms = set()
        for secret in secrets:
            forms.update((secret, quote(secret, safe=''), quote_plus(secret, safe=''),
                          json.dumps(secret)[1:-1], base64.b64encode(secret.encode()).decode(),
                          base64.urlsafe_b64encode(secret.encode()).decode().rstrip('=')))
        self._forms = sorted((_normalize(s) for s in forms), key=len, reverse=True)

    def _redact(self, value):
        value = _normalize(value)
        # Redact before truncation, including secrets straddling the excerpt limit.
        for secret in self._forms:
            value = value.replace(secret, '[REDACTED]')
        value = re.sub(r'-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)', '[REDACTED]', value)
        value = re.sub(r'(?i)\b(?:https?://\S+|Bearer\s+\S+|(?:github_pat_|gh[pousr]_)[A-Za-z0-9_]+)', '[REDACTED]', value)
        value = re.sub(r'[A-Za-z0-9_+/=.-]{24,}', '[REDACTED]', value)
        return ' '.join(value.split())

    def record(self, *, operation, status, headers, data):
        if operation != 'create_pr' or type(status) is not int or status != 422 or not isinstance(data, dict):
            return None
        candidates = [(None, data.get('message'))]
        errors = data.get('errors', [])
        if isinstance(errors, list):
            candidates.extend((i, e.get('message')) for i, e in enumerate(errors[:MAX_ERRORS]) if isinstance(e, dict))
        messages = []; remaining = MAX_DETAIL_BYTES; omitted = 0
        for index, value in candidates:
            if not isinstance(value, str) or _message(value) != 'unclassified':
                continue
            clean = self._redact(value).encode('utf-8')
            limit = min(remaining, MAX_MESSAGE_BYTES)
            if not limit:
                omitted += 1
                continue
            excerpt = clean[:limit].decode('utf-8', errors='ignore')
            if not excerpt:
                omitted += 1
                continue
            remaining -= len(excerpt.encode('utf-8'))
            messages.append({'error_index': index, 'excerpt': excerpt, 'truncated': len(clean) > limit})
        if not messages:
            return None
        record = {'schema_version': 1, 'scope': 'operator_diagnostic_only', 'operation': operation,
                  'http_status': status, 'github_request_id': _request_id(list(headers.items())),
                  'messages': messages, 'omitted_messages': omitted,
                  'errors_truncated': isinstance(errors, list) and len(errors) > MAX_ERRORS,
                  'redaction': 'known_credentials_and_common_shapes_v1',
                  'observed_at': datetime.now(timezone.utc).isoformat(), 'event_id': uuid4().hex}
        if len(json.dumps(record).encode()) > MAX_RECORD:
            raise ValueError('diagnostic_record_too_large')
        fd = _directory(self.directory)
        try:
            _write_new(fd, record['event_id']+'.json', record)
        finally:
            os.close(fd)
        return None  # Excerpts never reach the workflow result or stdout.
