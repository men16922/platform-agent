"""Local P5-E at-most-once attempt boundary, independent of a GitHub transport.

One private directory identifies ONE reviewed operation. A durable intent is the
point of no automatic retry, even if the process dies before sending. OBSERVED
means an HTTP observation was captured, never that publication was verified.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
from uuid import uuid4

from src.agents.platform.writer_capture import (
    MAX_RECORD, OPERATIONS, ResponseJournal, _decode, capture_http_response,
)


class AttemptError(ValueError):
    """Fixed codes only."""


def _directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    info = os.fstat(fd)
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        os.close(fd)
        raise AttemptError('attempt_directory_not_private')
    return fd


def _write_new(fd, name, record):
    raw = (json.dumps(record, sort_keys=True, separators=(',', ':'))+'\n').encode()
    output = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=fd)
    with os.fdopen(output, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.fsync(fd)
    # Interrupted/partial records intentionally remain: their existence bars retry.


def _read(fd, name):
    source = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    with os.fdopen(source, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > MAX_RECORD):
            raise AttemptError('invalid_attempt_record')
        data = _decode(stream.read(MAX_RECORD+1))
        if not isinstance(data, dict):
            raise AttemptError('invalid_attempt_record')
        return data


def _identifier(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{32}', value) is not None


def _inspect(fd):
    try:
        intent = _read(fd, 'intent.json')
    except FileNotFoundError:
        return {'state':'NOT_STARTED'}
    if (set(intent) != {'schema_version','attempt_id','operation','created_at'}
            or type(intent['schema_version']) is not int or intent['schema_version'] != 1
            or not _identifier(intent['attempt_id']) or intent['operation'] not in OPERATIONS
            or datetime.fromisoformat(intent['created_at']).utcoffset() is None):
        raise AttemptError('invalid_attempt_record')
    result = {'state':'UNKNOWN','attempt_id':intent['attempt_id'],'operation':intent['operation']}
    try:
        receipt = _read(fd, 'receipt.json')
    except FileNotFoundError:
        return result
    if (set(receipt) != {'attempt_id','operation','capture_event_id'}
            or receipt['attempt_id'] != intent['attempt_id'] or receipt['operation'] != intent['operation']
            or not _identifier(receipt['capture_event_id'])):
        raise AttemptError('invalid_attempt_record')
    observation = _read(fd, receipt['capture_event_id']+'.json')
    if (observation.get('event_id') != receipt['capture_event_id']
            or observation.get('operation') != intent['operation']
            or type(observation.get('schema_version')) is not int or observation['schema_version'] != 1):
        raise AttemptError('invalid_attempt_record')
    status = observation.get('http_status')
    if observation.get('transport') == 'response' and type(status) is int and 100 <= status <= 599:
        result.update(state='OBSERVED', http_status=status, capture_event_id=receipt['capture_event_id'])
    return result


def inspect_attempt(directory):
    """Read-only status; an incomplete/unreadable record is UNKNOWN, never success."""
    fd = None
    try:
        fd = _directory(directory)
        return _inspect(fd)
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        return {'state':'UNKNOWN','reason':'attempt_store_unavailable_or_invalid'}
    finally:
        if fd is not None:
            os.close(fd)


def run_once(directory, *, operation, send):
    """Invoke a trusted zero-argument sender only after durable, exclusive intent.

    The sender owns request configuration, credentials, timeouts and redirect
    policy. No client exists here. Existing intent blocks ANY future operation
    in this directory. There is no lease, reset, delete, retry or inferred success.
    """
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise AttemptError('invalid_attempt_operation')
    directory = Path(directory)
    fd = None
    try:
        fd = _directory(directory)
        intent = {'schema_version':1,'attempt_id':uuid4().hex,'operation':operation,
                  'created_at':datetime.now(timezone.utc).isoformat()}
        try:
            _write_new(fd, 'intent.json', intent)
        except FileExistsError:
            return {'state':'BLOCKED','reason':'attempt_already_started'}
        except OSError:
            return {'state':'UNKNOWN','reason':'intent_store_unavailable'}
        journal = ResponseJournal(directory)
        try:
            try:
                response = send()
            except TimeoutError:
                observation = journal.record(operation=operation, status=None, transport='timeout')
            except OSError:
                observation = journal.record(operation=operation, status=None, transport='connection_error')
            else:
                observation = capture_http_response(journal, response, operation=operation)
        except Exception:
            # Intent remains. Exception strings can contain URLs, request bodies or keys.
            return {'state':'UNKNOWN','reason':'send_or_capture_failed'}
        try:
            _write_new(fd, 'receipt.json', {'attempt_id':intent['attempt_id'],'operation':operation,
                                          'capture_event_id':observation['event_id']})
        except OSError:
            return {'state':'UNKNOWN','reason':'receipt_store_unavailable'}
        return _inspect(fd)
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        return {'state':'UNKNOWN','reason':'attempt_store_unavailable_or_invalid'}
    finally:
        if fd is not None:
            os.close(fd)
