"""Bounded P5-E response capture; observations never prove publication or denial.

Only fixed classifications and allowlisted metadata reach the private journal.
No request bodies, URLs, credentials, raw response text or exception text persist.
The caller must stop if capture fails, and reconcile writes after uncertain I/O.
"""
from datetime import datetime, timezone
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import stat
from uuid import uuid4

MAX_BODY = 64 * 1024
MAX_ERRORS = 16
MAX_RECORD = 8192
OPERATIONS = frozenset({'create_ref', 'write_target', 'write_sibling', 'create_pr',
                        'read_control', 'revoke_token'})
MESSAGES = {
    'Validation Failed': 'validation_failed', 'Invalid request': 'invalid_request',
    'Resource not accessible by integration': 'integration_access_error',
    'Resource not accessible by personal access token': 'token_access_error',
    'Bad credentials': 'bad_credentials', 'Requires authentication': 'authentication_required',
    'Not Found': 'not_found', 'Problems parsing JSON': 'invalid_json_request',
    'Body should be a JSON object': 'object_required', 'Server Error': 'server_error',
}
RESOURCES = frozenset({'PullRequest', 'Reference', 'Commit', 'Repository', 'Issue', 'Contents'})
FIELDS = frozenset({'head', 'base', 'sha', 'ref', 'title', 'body', 'content', 'branch',
                    'draft', 'maintainer_can_modify'})
CODES = frozenset({'missing', 'missing_field', 'invalid', 'already_exists', 'unprocessable', 'custom'})


class CaptureError(ValueError):
    """Fixed failure codes only; callers must never log the originating exception."""


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate_key')
        result[key] = value
    return result


def _nonfinite(_):
    raise ValueError('nonfinite')


def _decode(raw):
    text = raw.decode('utf-8')
    depth, quoted, escaped = 0, False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '{[':
            depth += 1
            if depth > 64:
                raise ValueError('excessive_json_depth')
        elif char in '}]':
            depth -= 1
    return json.loads(text, object_pairs_hook=_unique, parse_constant=_nonfinite)


def _message(value):
    if not isinstance(value, str):
        return 'unclassified'
    if value in MESSAGES:
        return MESSAGES[value]
    # Discard variable refs/repositories even for recognized custom diagnostics.
    if re.fullmatch(r'No commits between [A-Za-z0-9_./:-]{1,256} and [A-Za-z0-9_./:-]{1,256}', value):
        return 'no_commits_between'
    if re.fullmatch(r'A pull request already exists for [A-Za-z0-9_./:-]{1,256}\.?', value):
        return 'pull_request_already_exists'
    return 'unclassified'


def _body(raw):
    if not isinstance(raw, bytes):
        return {'body_state': 'unavailable', 'message_class': 'unclassified', 'errors': []}
    state = 'oversize' if len(raw) > MAX_BODY else 'empty' if not raw else 'invalid_json'
    data = None
    if raw and len(raw) <= MAX_BODY:
        try:
            data = _decode(raw)
            state = 'object' if isinstance(data, dict) else 'non_object'
        except (UnicodeError, ValueError, RecursionError):
            pass
    result = {'body_state': state, 'message_class': 'unclassified', 'errors': []}
    if state != 'object':
        return result
    result['message_class'] = _message(data.get('message'))
    errors = data.get('errors', [])
    result['errors_state'] = 'absent' if 'errors' not in data else 'list' if isinstance(errors, list) else 'invalid'
    if not isinstance(errors, list):
        return result
    result['errors_truncated'] = len(errors) > MAX_ERRORS
    for error in errors[:MAX_ERRORS]:
        if not isinstance(error, dict):
            result['errors'].append({'message_class': 'unclassified'})
            continue
        # Unknown values become null; free-form custom error messages are not retained.
        clean = {}
        for key, allowed in [('resource', RESOURCES), ('field', FIELDS), ('code', CODES)]:
            value = error.get(key)
            clean[key] = value if isinstance(value, str) and value in allowed else None
        clean['message_class'] = _message(error.get('message'))
        result['errors'].append(clean)
    return result


def _request_id(headers):
    # Preserve only GitHub's observed colon-separated hexadecimal request ID shape.
    # Ambiguous duplicate headers, CR/LF and unfamiliar shapes are discarded.
    if not isinstance(headers, (list, tuple)) or len(headers) > 128:
        return None
    values = []
    for pair in headers:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            return None
        key, value = pair
        if isinstance(key, str) and key.lower() == 'x-github-request-id':
            values.append(value)
    if len(values) == 1 and isinstance(values[0], str) and re.fullmatch(
            r'[0-9A-Fa-f]{1,16}(?::[0-9A-Fa-f]{1,16}){4}', values[0]):
        return values[0]
    return None


def sanitize_response(*, operation, status, headers=(), body=None, transport='response'):
    """Allowlist projection of an untrusted response, with no success inference."""
    if (not isinstance(operation, str) or operation not in OPERATIONS
            or not isinstance(transport, str)
            or transport not in ('response', 'timeout', 'connection_error', 'body_unavailable')):
        raise CaptureError('invalid_capture_context')
    if status is not None and (type(status) is not int or not 100 <= status <= 599):
        raise CaptureError('invalid_capture_context')
    if (transport == 'response' and status is None) or (transport in ('timeout', 'connection_error') and status is not None):
        raise CaptureError('invalid_capture_context')
    return {'schema_version': 1, 'operation': operation, 'http_status': status,
            'transport': transport, 'github_request_id': _request_id(headers),
            **_body(body if transport == 'response' else None)}


class ResponseJournal:
    """One bounded atomic JSON file per observation in an existing private directory.

    Only this class generates filenames. Directory is trusted server configuration;
    final-component symlinks, shared permissions and a different owner are refused.
    A failure (including fsync) is not a successful capture, even if a file remains.
    """
    def __init__(self, directory):
        self.directory = Path(directory)

    def record(self, *, operation, status, headers=(), body=None, transport='response'):
        record = sanitize_response(operation=operation, status=status, headers=headers,
                                   body=body, transport=transport)
        event_id = uuid4().hex
        record = {**record, 'event_id': event_id, 'observed_at': datetime.now(timezone.utc).isoformat()}
        raw = (json.dumps(record, sort_keys=True, separators=(',', ':')) + '\n').encode()
        if len(raw) > MAX_RECORD:
            raise CaptureError('capture_record_too_large')
        directory_fd = None
        temporary = '.' + event_id + '.pending'
        filename = event_id + '.json'
        try:
            directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            info = os.fstat(directory_fd)
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise CaptureError('capture_directory_not_private')
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=directory_fd)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            # A link publishes a fully written inode without overwriting an existing event.
            os.link(temporary, filename, src_dir_fd=directory_fd, dst_dir_fd=directory_fd,
                    follow_symlinks=False)
            os.unlink(temporary, dir_fd=directory_fd)
            os.fsync(directory_fd)
        except CaptureError:
            raise
        except OSError:
            raise CaptureError('capture_store_unavailable') from None
        finally:
            if directory_fd is not None:
                try:
                    os.unlink(temporary, dir_fd=directory_fd)
                except FileNotFoundError:
                    pass
                except OSError:
                    raise CaptureError('capture_store_unavailable') from None
                finally:
                    os.close(directory_fd)
        return record


def capture_http_response(journal, response, *, operation):
    """Consume and close a stdlib HTTPResponse/HTTPError, then persist before returning.

    Reading is bounded even for chunked/no-length responses. The network caller
    owns socket timeouts and must not retry a write based on this diagnostic record.
    """
    status = response.status
    headers = response.getheaders() if hasattr(response, 'getheaders') else list(response.headers.items())
    try:
        try:
            body = response.read(MAX_BODY + 1)
            transport = 'response'
        except (OSError, EOFError, HTTPException):
            body, transport = None, 'body_unavailable'
    finally:
        response.close()
    return journal.record(operation=operation, status=status, headers=headers,
                          body=body, transport=transport)
