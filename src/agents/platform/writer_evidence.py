"""Offline consistency checker for the bounded P5-E experiment, not a GitHub client.

Observations and denial controls must be collected independently. This module
cannot authenticate their provenance or prove that a live experiment occurred.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import re

LAB = Path(__file__).resolve().parents[3] / 'experiments/phase5-writer'
TARGET = 'platform/tenants/acme.yaml'
SIBLING = 'platform/tenants/globex.yaml'
BASE_KEYS = frozenset({'schema_version', 'repository', 'expected_identity',
                      'credential_control', 'seed', 'branch_origin', 'selected_branch'})
STAGE_KEYS = {'preflight': BASE_KEYS}
for _stage, _fields in [('create_ref', {'branch', 'branch_snapshot'}),
                       ('write_target', {'target'}), ('write_sibling', {'sibling'}),
                       ('create_pr', {'pull_request'})]:
    STAGE_KEYS[_stage] = list(STAGE_KEYS.values())[-1] | _fields


class InvalidEvidence(ValueError):
    """A fixed reason code, never input content or credentials."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise InvalidEvidence(reason)


def _sha(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{40}', value) is not None


def _blob(content: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()


def _snapshot(value, expected_ref):
    _require(isinstance(value, dict), 'missing_snapshot')
    _require(value.get('ref') == expected_ref, 'wrong_snapshot_ref')
    _require(value.get('observer') == 'operator' and value.get('complete') is True,
             'incomplete_operator_snapshot')
    _require(_sha(value.get('commit')) and _sha(value.get('main')), 'invalid_snapshot_sha')
    _require(isinstance(value.get('parents'), list)
             and all(_sha(parent) for parent in value['parents']), 'invalid_parents')
    _require(isinstance(value.get('files'), dict), 'invalid_tree')
    for path, entry in value['files'].items():
        _require(isinstance(path, str) and isinstance(entry, dict)
                 and _sha(entry.get('sha')) and isinstance(entry.get('mode'), str), 'invalid_tree')
    return value


def _exact_json(left, right) -> bool:
    # Python equality treats True == 1 and 1.0 == 1; captured JSON types matter.
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def _call(value, method, path, body):
    _require(isinstance(value, dict), 'missing_call')
    _require(value.get('identity') == 'installation-token', 'wrong_call_identity')
    _require(value.get('method') == method and value.get('path') == path
             and _exact_json(value.get('body'), body), 'wrong_call_request')
    status = value.get('status')
    _require(status is None or (type(status) is int and 100 <= status <= 599), 'invalid_status')
    return status


def _denied(call) -> bool:
    # These are normalized observations, not facts inferred from 403/404 alone.
    controls = call.get('denial_controls', {})
    return call.get('status') in (403, 404) and all(
        controls.get(key) is True for key in (
            'token_valid', 'target_exists', 'sha_matches', 'rate_limit_excluded',
        )
    )


def _result(verdict, reason, boundary='not_tested'):
    return {'scope': 'offline_evidence_consistency', 'verdict': verdict,
            'reason': reason, 'sibling_boundary': boundary, 'live_verified': False}


def judge(evidence) -> dict:
    """Judge normalized observations against the committed experiment fixtures.

    supported means internally consistent supplied evidence for all four calls.
    diagnostic_only never implies the automatic branch-creation flow succeeded.
    Invalid/missing observations fail closed to inconclusive; they are not denials.
    """
    try:
        result = _judge(evidence)
    except InvalidEvidence as error:
        result = _result('inconclusive', str(error))
    except (KeyError, TypeError, AttributeError, RecursionError):
        result = _result('inconclusive', 'invalid_or_incomplete_evidence')
    result['diagnostic_only'] = isinstance(evidence, dict) and evidence.get('branch_origin') == 'operator'
    return result


def validate_stage(evidence, stage, *, policy_root=None):
    """Validate only an observed prefix; never synthesize successful later calls."""
    if stage not in ('preflight', 'create_ref', 'write_target', 'write_sibling', 'create_pr'):
        return _result('inconclusive', 'invalid_stage')
    if not isinstance(evidence, dict) or set(evidence) != STAGE_KEYS[stage]:
        return _result('inconclusive', 'invalid_stage_fields')
    try:
        return _judge(evidence, stop_after=stage, policy_root=policy_root)
    except InvalidEvidence as error:
        return _result('inconclusive', str(error))
    except (KeyError, TypeError, AttributeError, RecursionError):
        return _result('inconclusive', 'invalid_or_incomplete_evidence')


def _judge(e, *, stop_after=None, policy_root=None):
    policy_root = LAB if policy_root is None else Path(policy_root)
    _require(isinstance(e, dict) and type(e.get('schema_version')) is int
             and e['schema_version'] == 1, 'invalid_schema')
    policy = json.loads((policy_root / 'review.json').read_text())
    repo = policy['repository']
    _require(e.get('repository') == repo, 'wrong_repository')
    ids = e['expected_identity']
    _require(set(ids) == {'app_id', 'installation_id', 'repository_id'}
             and all(type(ids.get(k)) is int and ids[k] > 0
                 for k in ('app_id', 'installation_id', 'repository_id')), 'invalid_identity_ids')
    control = e['credential_control']
    _require(control.get('identity') == 'installation-token'
             and type(control.get('status')) is int and control['status'] == 200
             and control.get('repository') == repo
             and all(type(control.get(k)) is int and control[k] == ids[k] for k in ids)
             and control.get('permissions') == policy['permissions']
             and control.get('single_file_paths') == policy['single_file_paths']
             and _exact_json(control.get('repository_selection'), [ids['repository_id']]), 'unverified_credential')
    seed_files = {p: {'mode': '100644', 'sha': _blob((policy_root / 'seed' / p).read_bytes())}
                  for p in (TARGET, SIBLING)}
    changed_files = {**seed_files, TARGET: {
        'mode': '100644', 'sha': _blob((policy_root / 'expected/acme.yaml').read_bytes()),
    }}
    seed = _snapshot(e['seed'], 'main')
    _require(seed['files'] == seed_files and seed['main'] == seed['commit'], 'wrong_seed')
    base = seed['commit']
    if stop_after == 'preflight':
        _require(e.get('branch_origin') in ('app', 'operator'), 'invalid_branch_origin')
        selected = policy['diagnostic_branch'] if e['branch_origin'] == 'operator' else policy['branch']
        _require(e.get('selected_branch') == selected, 'wrong_branch')
        return _result('stage_verified', 'credential_and_seed_verified')
    branch = e['branch']
    branch_status = _call(branch, 'POST', f'/repos/{repo}/git/refs',
                          {'ref': 'refs/heads/' + policy['branch'], 'sha': base})
    diagnostic = e.get('branch_origin') == 'operator'
    _require(e.get('branch_origin') in ('app', 'operator'), 'invalid_branch_origin')
    if diagnostic:
        _require(_denied(branch) and branch.get('observed_absent') is True
                 and branch.get('main_sha') == base, 'unproven_branch_denial')
        selected = policy['diagnostic_branch']
        _require(e.get('selected_branch') == selected, 'wrong_diagnostic_branch')
    else:
        selected = policy['branch']
        _require(e.get('selected_branch') == selected, 'wrong_branch')
        if branch_status != 201:
            # Never ignore later calls after an unsuccessful prerequisite.
            _require(not any(e.get(k) for k in ('target', 'sibling', 'pull_request')),
                     'calls_after_failed_branch')
            if (_denied(branch) and branch.get('observed_absent') is True
                    and branch.get('main_sha') == base):
                return _result('unsupported', 'app_branch_creation_denied')
            return _result('inconclusive', 'branch_creation_not_proven')
        _require(branch.get('response') == {'ref': 'refs/heads/' + selected,
                                          'object': {'sha': base}}, 'branch_response_mismatch')
    branch_seed = {**seed, 'ref': selected}
    _require(_snapshot(e['branch_snapshot'], selected) == branch_seed, 'branch_not_at_seed')
    if stop_after == 'create_ref':
        return _result('stage_verified', 'branch_snapshot_verified')
    target = e['target']
    target_status = _call(target, 'PUT', f'/repos/{repo}/contents/{TARGET}', {
        'branch': selected, 'sha': seed_files[TARGET]['sha'],
        'content': base64.b64encode((policy_root / 'expected/acme.yaml').read_bytes()).decode(),
    })
    _require(_snapshot(target['before'], selected) == branch_seed, 'target_before_mismatch')
    after = _snapshot(target['after'], selected)
    if target_status != 200:
        if after != branch_seed:
            return _result('boundary_failure', 'unexpected_target_change')
        _require(not e.get('sibling') and not e.get('pull_request'), 'calls_after_failed_target')
        return _result('unsupported' if _denied(target) else 'inconclusive',
                       'target_write_not_proven')
    if after['files'] != changed_files or after['main'] != base:
        return _result('boundary_failure', 'unexpected_target_tree_or_main')
    _require(after['commit'] != base and after['parents'] == [base], 'wrong_target_parent')
    _require(target.get('response') == {'commit_sha': after['commit'],
                                       'blob_sha': changed_files[TARGET]['sha']}, 'target_response_mismatch')
    if stop_after == 'write_target':
        return _result('stage_verified', 'target_snapshot_verified')
    sibling = e['sibling']
    sibling_status = _call(sibling, 'PUT', f'/repos/{repo}/contents/{SIBLING}', {
        'branch': selected, 'sha': seed_files[SIBLING]['sha'],
        'content': base64.b64encode((policy_root / 'expected/globex.yaml').read_bytes()).decode(),
    })
    _require(_snapshot(sibling['before'], selected) == after, 'sibling_before_mismatch')
    if sibling_status is not None and 200 <= sibling_status < 300:
        return _result('boundary_failure', 'sibling_write_or_tree_change', 'violated')
    sibling_after = _snapshot(sibling['after'], selected)
    if sibling_after != after:
        return _result('boundary_failure', 'sibling_write_or_tree_change', 'violated')
    if not _denied(sibling):
        return _result('inconclusive', 'sibling_denial_not_proven', 'inconclusive')
    if stop_after == 'write_sibling':
        return _result('stage_verified', 'sibling_denial_verified', 'supported')
    pr = e.get('pull_request')
    if not pr:
        return _result('inconclusive', 'pr_not_observed', 'supported')
    pr_status = _call(pr, 'POST', f'/repos/{repo}/pulls', {
        'head': selected, 'base': 'main', 'draft': True, 'maintainer_can_modify': False,
    })
    final = _snapshot(pr['after'], selected)
    if final != after:
        return _result('boundary_failure', 'pr_changed_tree_or_main', 'supported')
    if pr_status != 201:
        return _result('inconclusive', 'pr_creation_not_proven', 'supported')
    response = pr['response']
    number = response.get('number')
    _require(type(number) is int and number > 0
             and response.get('url') == f'https://github.com/{repo}/pull/{number}'
             and type(response.get('author_app_id')) is int
             and response['author_app_id'] == ids['app_id']
             and response.get('head') == {'ref': selected, 'sha': after['commit'], 'repo': repo}
             and response.get('base') == {'ref': 'main', 'sha': base, 'repo': repo}
             and response.get('draft') is True and response.get('merged') is False,
             'pr_response_mismatch')
    files = pr['files']
    _require(type(files.get('status')) is int and files['status'] == 200 and files.get('complete') is True
             and files.get('identity') == 'installation-token'
             and files.get('method') == 'GET'
             and files.get('path') == f'/repos/{repo}/pulls/{number}/files?per_page=100'
             and _exact_json(files.get('items'), [{'filename': TARGET, 'status': 'modified',
                 'additions': 1, 'deletions': 0, 'sha': changed_files[TARGET]['sha']}]),
             'pr_files_mismatch')
    return _result('diagnostic_only' if diagnostic else 'supported',
                   'four_call_evidence_consistent', 'supported')
