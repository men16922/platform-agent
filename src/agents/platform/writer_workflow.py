"""Reviewed P5-E stage controller with fixed attempts and independent observations.

The two callbacks are trusted adapters: send owns the bound installation token,
observe uses independent reads. Neither model prose nor response text can choose
requests or advance stages. This module ships no live GitHub client or credentials.
"""
from dataclasses import dataclass
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path

from src.agents.platform.writer_attempt import _directory, _read, _write_new, inspect_attempt, run_once
from src.agents.platform.writer_evidence import LAB, TARGET, SIBLING, STAGE_KEYS, validate_stage
from src.agents.platform.writer_capture import _decode

STAGES = ('create_ref', 'write_target', 'write_sibling', 'create_pr')
CALL_KEYS = dict(create_ref='branch', write_target='target', write_sibling='sibling', create_pr='pull_request')


class WorkflowError(ValueError):
    """Fixed reason codes only."""


def _copy(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if len(raw) > 1024 * 1024:
        raise WorkflowError('observation_too_large')
    return _decode(raw)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _policy_digest(policy_root):
    paths = ['review.json', 'seed/'+TARGET, 'seed/'+SIBLING, 'expected/acme.yaml', 'expected/globex.yaml']
    return _digest({name:hashlib.sha256((policy_root/name).read_bytes()).hexdigest() for name in paths})


def _prefix(evidence, stage):
    return {key:evidence[key] for key in STAGE_KEYS[stage]}


def _validate(evidence, stage, policy_root):
    result = validate_stage(evidence, stage, policy_root=policy_root)
    accepted = ('supported', 'diagnostic_only') if stage == 'create_pr' else ('stage_verified',)
    if result['verdict'] not in accepted:
        raise WorkflowError(result['reason'])


def _observe(observer, phase, stage):
    try:
        return _copy(observer(phase, stage))
    except Exception:
        raise WorkflowError('observer_unavailable') from None


@dataclass(frozen=True)
class RequestSpec:
    operation: str
    method: str
    path: str
    body: str | None


def _request(review, operation, policy_root=LAB):
    repo, branch = review['repository'], review['selected_branch']
    if operation == 'revoke_token':
        return RequestSpec(operation, 'DELETE', '/installation/token', None)
    if operation == 'create_ref':
        method, path = 'POST', f'/repos/{repo}/git/refs'
        body = {'ref':'refs/heads/'+branch, 'sha':review['seed']['commit']}
    elif operation in ('write_target', 'write_sibling'):
        target = TARGET if operation == 'write_target' else SIBLING
        filename = 'acme.yaml' if operation == 'write_target' else 'globex.yaml'
        method, path = 'PUT', f'/repos/{repo}/contents/{target}'
        body = {'branch':branch, 'sha':review['seed']['files'][target]['sha'],
                'content':base64.b64encode((policy_root/'expected'/filename).read_bytes()).decode(),
                'message':'P5-E synthetic permission boundary probe'}
    else:
        method, path = 'POST', f'/repos/{repo}/pulls'
        body = {'head':branch, 'base':'main', 'draft':True, 'maintainer_can_modify':False,
                'title':'P5-E synthetic permission boundary probe'}
    return RequestSpec(operation, method, path, json.dumps(body, sort_keys=True, separators=(',', ':')))


def _slot(directory, fd, operation):
    try:
        os.mkdir(operation, mode=0o700, dir_fd=fd)
        os.fsync(fd)
    except FileExistsError:
        pass
    path = directory / operation
    child = _directory(path)
    os.close(child)
    return path


def _expected_snapshot(evidence, prior):
    if prior == 'preflight':
        return evidence['seed']
    if prior == 'create_ref':
        return evidence['branch_snapshot']
    return evidence[CALL_KEYS[prior]]['after']


def _open_workflow_lock(fd):
    # Local macOS concurrent creation returned transient ENOENT despite O_CREAT
    # (dogfood-20261003/repeats/writer-concurrency-diagnostic.json). Retry only
    # this local open, before acquiring the lock or making any external call.
    # Keep O_NOFOLLOW and fail closed on persistent absence or any other error.
    for attempt in range(3):
        try:
            return os.open('workflow.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        except FileNotFoundError:
            if attempt == 2:
                raise


def _verify_saved(directory, proof, evidence, stage, scope_id):
    observed = inspect_attempt(directory/stage)
    if (set(proof) != {'scope_id','operation','evidence_digest','attempt_id','http_status'}
            or proof['scope_id'] != scope_id or proof['operation'] != stage
            or proof['evidence_digest'] != _digest(_prefix(evidence, stage))
            or observed.get('state') != 'OBSERVED'
            or proof['attempt_id'] != observed.get('attempt_id')
            or type(proof['http_status']) is not int
            or proof['http_status'] != observed.get('http_status')):
        raise WorkflowError('previous_observation_changed')


def _cleanup(directory, fd, review, send, observe):
    """One revocation attempt, then independent same-credential invalidity read."""
    try:
        slot = _slot(directory, fd, 'revoke_token')
        outcome = run_once(slot, operation='revoke_token', send=lambda:send(_request(review,'revoke_token')))
        if outcome.get('state') == 'BLOCKED':
            outcome = inspect_attempt(slot)  # read only; never retry a lost revoke
        if outcome.get('state') != 'OBSERVED' or outcome.get('http_status') != 204:
            return 'UNVERIFIED'
        control = _observe(observe, 'after', 'revoke_token')
        expected = {'expected_identity':review['expected_identity'], 'identity':'installation-token',
                    'method':'GET', 'path':'/installation/repositories', 'status':401}
        if _digest(control) == _digest(expected):
            return 'OBSERVED_INVALID'
    except Exception:
        pass
    return 'UNVERIFIED'


def execute_workflow(root, review, *, send, observe, policy_root=None):
    """Run a fixed reviewed flow, retaining every stop across normal restarts.

    Before each write, observe('before', operation) supplies evidence through the
    previous stage plus current_snapshot; after it, observe('after', operation)
    supplies the next cumulative prefix. Only bounded digests of these observations
    persist. The review is trusted server data, never an HTTP/model request body.
    """
    root_fd = fd = lock_fd = None
    result = {'state':'UNKNOWN', 'reason':'workflow_store_or_context_invalid', 'cleanup':'NOT_ATTEMPTED',
              'live_verified':False, 'diagnostic_only':False}
    try:
        policy_root = LAB if policy_root is None else Path(policy_root)
        review = _copy(review)
        diagnostic = review.get('branch_origin') == 'operator'
        initial = 'create_ref' if diagnostic else 'preflight'
        _validate(review, initial, policy_root)
        policy_digest = _policy_digest(policy_root)
        scope_id = _digest({'repository':review['repository'], 'identity':review['expected_identity'],
                           'base_commit':review['seed']['commit'], 'branch':review['selected_branch'],
                           'branch_origin':review['branch_origin']})
        binding = {'schema_version':1,'review_digest':_digest(review),'policy_digest':policy_digest}
        root_fd = _directory(root)
        try:
            os.mkdir(scope_id, mode=0o700, dir_fd=root_fd)
            os.fsync(root_fd)
        except FileExistsError:
            pass
        directory = Path(root)/scope_id
        fd = _directory(directory)
        lock_fd = _open_workflow_lock(fd)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {**result,'state':'BLOCKED','reason':'workflow_running'}
        try:
            _write_new(fd, 'scope.json', binding)
        except FileExistsError:
            if _digest(_read(fd, 'scope.json')) != _digest(binding):
                return {**result,'state':'BLOCKED','reason':'review_binding_changed'}
        try:
            _read(fd, 'result.json')
        except FileNotFoundError:
            pass
        else:
            return {**result,'state':'BLOCKED','reason':'workflow_already_finished'}
        result['diagnostic_only'] = diagnostic
        try:
            prior = initial
            saved = {}
            for stage in (STAGES[1:] if diagnostic else STAGES):
                if _policy_digest(policy_root) != policy_digest:
                    raise WorkflowError('review_policy_changed')
                try:
                    proof = _read(fd, stage+'.verified.json')
                except FileNotFoundError:
                    proof = None
                if proof is not None:
                    saved[stage] = proof
                    prior = stage
                    continue
                slot = _slot(directory, fd, stage)
                if inspect_attempt(slot).get('state') != 'NOT_STARTED':
                    result.update(state='UNKNOWN',reason='attempt_unresolved')
                    break
                frame = _observe(observe, 'before', stage)
                if not isinstance(frame, dict) or set(frame) != {'evidence','current_snapshot'}:
                    raise WorkflowError('invalid_pre_write_observation')
                evidence = frame['evidence']
                _validate(evidence, prior, policy_root)
                if _digest(_prefix(evidence, initial)) != _digest(review):
                    raise WorkflowError('review_observation_changed')
                for earlier, recorded in saved.items():
                    _verify_saved(directory, recorded, evidence, earlier, scope_id)
                if _digest(frame['current_snapshot']) != _digest(_expected_snapshot(evidence, prior)):
                    raise WorkflowError('current_snapshot_changed')
                if _policy_digest(policy_root) != policy_digest:
                    raise WorkflowError('review_policy_changed')
                outcome = run_once(slot, operation=stage, send=lambda:send(_request(review,stage,policy_root)))
                if outcome.get('state') != 'OBSERVED':
                    result.update(state='UNKNOWN',reason='attempt_unresolved')
                    break
                attempt_fd = _directory(slot)
                try:
                    capture = _read(attempt_fd, outcome['capture_event_id']+'.json')
                finally:
                    os.close(attempt_fd)
                if capture.get('body_state') != 'object':
                    result.update(state='UNKNOWN',reason='response_body_unusable')
                    break
                after = _observe(observe, 'after', stage)
                if _policy_digest(policy_root) != policy_digest:
                    raise WorkflowError('review_policy_changed')
                if _digest(_prefix(after, prior)) != _digest(evidence):
                    raise WorkflowError('previous_observation_changed')
                call = after.get(CALL_KEYS[stage], {})
                if type(call.get('status')) is not int or call['status'] != outcome['http_status']:
                    raise WorkflowError('captured_status_mismatch')
                _validate(after, stage, policy_root)
                proof = {'scope_id':scope_id, 'operation':stage, 'evidence_digest':_digest(after),
                         'attempt_id':outcome['attempt_id'], 'http_status':outcome['http_status']}
                _write_new(fd, stage+'.verified.json', proof)
                saved[stage] = proof
                prior = stage
            else:
                # A restart after all proof writes still needs fresh complete evidence.
                final = _observe(observe, 'after', 'create_pr')
                if _policy_digest(policy_root) != policy_digest:
                    raise WorkflowError('review_policy_changed')
                _validate(final, 'create_pr', policy_root)
                if _digest(_prefix(final, initial)) != _digest(review):
                    raise WorkflowError('review_observation_changed')
                for earlier, recorded in saved.items():
                    _verify_saved(directory, recorded, final, earlier, scope_id)
                result.update(state='CONSISTENT',reason='four_call_evidence_consistent')
        except WorkflowError as error:
            result.update(state='STOPPED',reason=str(error))
        except Exception:
            result.update(state='UNKNOWN',reason='observation_or_storage_unavailable')
        finally:
            result['cleanup'] = _cleanup(directory, fd, review, send, observe)
        if result['state'] == 'CONSISTENT' and result['cleanup'] != 'OBSERVED_INVALID':
            result.update(state='UNKNOWN', reason='cleanup_unverified')
        _write_new(fd, 'result.json', result)
        return result
    except Exception:
        return {**result,'state':'UNKNOWN','reason':'workflow_store_or_context_invalid'}
    finally:
        for handle in (lock_fd, fd, root_fd):
            if handle is not None:
                os.close(handle)
