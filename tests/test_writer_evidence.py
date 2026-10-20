"""Judge synthetic captured observations, without mocking an AWS/GitHub service."""
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from src.agents.platform.writer_evidence import judge

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'experiments/phase5-writer/fixtures/supported.synthetic.json'


@pytest.fixture
def evidence():
    return json.loads(FIXTURE.read_text())


def set_value(document, path, value):
    parts = path.split('.')
    for part in parts[:-1]:
        document = document[int(part)] if isinstance(document, list) else document[part]
    if isinstance(document, list):
        document[int(parts[-1])] = value
    else:
        document[parts[-1]] = value


def denial(call):
    call['status'] = 403
    call['denial_controls'] = {key: True for key in (
        'token_valid', 'target_exists', 'sha_matches', 'rate_limit_excluded',
    )}


def stop_at(evidence, stage):
    if stage == 'branch':
        for key in ('target', 'sibling', 'pull_request'):
            evidence.pop(key, None)
        evidence['branch']['observed_absent'] = True
        evidence['branch']['main_sha'] = evidence['seed']['commit']
    elif stage == 'target':
        evidence['target']['after'] = copy.deepcopy(evidence['branch_snapshot'])
        evidence.pop('sibling', None)
        evidence.pop('pull_request', None)


def diagnostic(evidence):
    denial(evidence['branch'])
    evidence['branch']['observed_absent'] = True
    evidence['branch']['main_sha'] = evidence['seed']['commit']
    evidence['branch_origin'] = 'operator'
    selected = evidence['selected_branch'] + '-diagnostic'
    evidence['selected_branch'] = selected
    evidence['branch_snapshot']['ref'] = selected
    for step in ('target', 'sibling', 'pull_request'):
        for key in ('before', 'after'):
            if key in evidence[step]:
                evidence[step][key]['ref'] = selected
    for key in ('target', 'sibling'):
        evidence[key]['body']['branch'] = selected
    evidence['pull_request']['body']['head'] = selected
    evidence['pull_request']['response']['head']['ref'] = selected


def test_complete_supplied_evidence_supports_only_offline_consistency(evidence):
    before = copy.deepcopy(evidence)
    result = judge(evidence)
    assert result == dict(scope='offline_evidence_consistency', verdict='supported',
                         reason='four_call_evidence_consistent', sibling_boundary='supported',
                         live_verified=False, diagnostic_only=False)
    assert evidence == before


def test_operator_branch_never_proves_automatic_flow(evidence):
    diagnostic(evidence)
    assert judge(evidence)['verdict'] == 'diagnostic_only'
    assert judge(evidence)['diagnostic_only'] is True


def test_diagnostic_marker_survives_target_denial(evidence):
    diagnostic(evidence)
    denial(evidence['target'])
    stop_at(evidence, 'target')
    result = judge(evidence)
    assert result['verdict'] == 'unsupported' and result['diagnostic_only'] is True
    assert result['sibling_boundary'] == 'not_tested'


@pytest.mark.parametrize('stage', ['branch', 'target', 'sibling', 'pull_request'])
@pytest.mark.parametrize('status', [401, 409, 422, 429, 503, None, 302])
def test_uncertain_status_never_counts_as_permission_denial_or_success(evidence, stage, status):
    stop_at(evidence, stage)
    evidence[stage]['status'] = status
    assert judge(evidence)['verdict'] == 'inconclusive'


@pytest.mark.parametrize('stage', ['branch', 'target', 'sibling'])
@pytest.mark.parametrize('status', [403, 404])
def test_denial_requires_controls_and_unchanged_observations(evidence, stage, status):
    stop_at(evidence, stage)
    denial(evidence[stage])
    evidence[stage]['status'] = status
    expected = 'supported' if stage == 'sibling' else 'unsupported'
    assert judge(evidence)['verdict'] == expected
    del evidence[stage]['denial_controls']
    assert judge(evidence)['verdict'] == 'inconclusive'


@pytest.mark.parametrize('control', ['token_valid', 'target_exists', 'sha_matches', 'rate_limit_excluded'])
@pytest.mark.parametrize('value', [False, 'true'])
def test_ambiguous_404_is_not_positive_boundary_evidence(evidence, control, value):
    evidence['sibling']['status'] = 404
    evidence['sibling']['denial_controls'][control] = value
    assert judge(evidence)['sibling_boundary'] == 'inconclusive'


@pytest.mark.parametrize('status', [200, 201, 204])
def test_sibling_2xx_is_a_boundary_failure_even_without_after_snapshot(evidence, status):
    evidence['sibling']['status'] = status
    del evidence['sibling']['after']
    result = judge(evidence)
    assert result['verdict'] == 'boundary_failure' and result['sibling_boundary'] == 'violated'


@pytest.mark.parametrize('stage', ['target', 'sibling', 'pull_request'])
def test_main_change_is_detected_even_with_expected_http_status(evidence, stage):
    evidence[stage]['after']['main'] = 'c'*40
    assert judge(evidence)['verdict'] == 'boundary_failure'


def test_same_branch_head_with_changed_sibling_blob_is_still_a_failure(evidence):
    evidence['sibling']['after']['files']['platform/tenants/globex.yaml']['sha'] = 'c'*40
    assert judge(evidence)['verdict'] == 'boundary_failure'


@pytest.mark.parametrize('change', ['sibling', 'extra_file', 'target_mode'])
def test_target_success_must_equal_the_exact_fixture_tree(evidence, change):
    files = evidence['target']['after']['files']
    if change == 'extra_file':
        files['unexpected.yaml'] = dict(mode='100644', sha='c'*40)
    elif change == 'target_mode':
        files['platform/tenants/acme.yaml']['mode'] = '120000'
    else:
        files['platform/tenants/globex.yaml']['sha'] = 'c'*40
    assert judge(evidence)['verdict'] == 'boundary_failure'


@pytest.mark.parametrize('path,value', [
    ('repository', 'men16922/platform-agent'),
    ('schema_version', True),
    ('expected_identity.app_id', True),
    ('credential_control.identity', 'operator'),
    ('credential_control.app_id', 999),
    ('credential_control.repository_selection', [789, 999]),
    ('credential_control.permissions.contents', 'write'),
    ('credential_control.single_file_paths', ['platform/tenants/globex.yaml']),
    ('branch.identity', 'operator'),
    ('target.identity', 'app-jwt'),
    ('sibling.identity', 'operator'),
    ('pull_request.identity', 'operator'),
    ('branch.response.object.sha', 'c'*40),
    ('branch_snapshot.complete', False),
    ('branch_snapshot.ref', 'main'),
    ('target.after.ref', 'unrelated-branch'),
    ('pull_request.files.identity', 'operator'),
    ('pull_request.files.path', '/repos/foreign/lab/pulls/2/files?per_page=100'),
    ('target.before.commit', 'c'*40),
    ('target.body.sha', 'c'*40),
    ('target.response.blob_sha', 'c'*40),
    ('sibling.body.sha', 'c'*40),
    ('sibling.path', '/repos/other/lab/contents/platform/tenants/globex.yaml'),
    ('pull_request.body.draft', 1),
    ('pull_request.response.author_app_id', 999),
    ('pull_request.response.url', 'https://github.com.evil.test/lab/pull/1'),
    ('pull_request.response.head.sha', 'c'*40),
    ('pull_request.response.base.sha', 'c'*40),
    ('pull_request.response.draft', False),
    ('pull_request.response.merged', True),
    ('pull_request.files.complete', False),
    ('pull_request.files.items.0.additions', 2),
    ('pull_request.files.items.0.deletions', 1),
])
def test_inconsistent_or_wrong_identity_evidence_cannot_support_flow(evidence, path, value):
    set_value(evidence, path, value)
    assert judge(evidence)['verdict'] == 'inconclusive'


@pytest.mark.parametrize('field', ['credential_control', 'branch', 'target', 'sibling', 'pull_request'])
def test_missing_step_cannot_be_filled_in_by_a_later_success(evidence, field):
    del evidence[field]
    assert judge(evidence)['verdict'] == 'inconclusive'


def test_target_denial_cannot_be_followed_by_affirmative_sibling_evidence(evidence):
    denial(evidence['target'])
    evidence['target']['after'] = copy.deepcopy(evidence['branch_snapshot'])
    assert judge(evidence)['verdict'] == 'inconclusive'


@pytest.mark.parametrize('value', [None, [], {}, {'schema_version': 1}, {'schema_version': '1'}])
def test_bad_input_is_inconclusive_without_echoing_input(value):
    assert judge(value)['verdict'] == 'inconclusive'


def test_cli_json_result_and_non_success_exit(tmp_path, evidence):
    path = tmp_path/'evidence.json'
    for expected, status in [(0, 403), (1, 401)]:
        evidence['sibling']['status'] = status
        path.write_text(json.dumps(evidence))
        proc = subprocess.run([sys.executable, 'scripts/judge_registry_writer.py', str(path)],
                              cwd=ROOT, capture_output=True, text=True, timeout=10)
        assert proc.returncode == expected and proc.stderr == ''
        assert json.loads(proc.stdout)['live_verified'] is False


@pytest.mark.parametrize('kind', ['invalid_json', 'missing', 'oversize'])
def test_cli_input_error_preserves_document_stdout_and_does_not_echo_secrets(tmp_path, kind):
    path = tmp_path/'evidence.json'
    if kind != 'missing':
        path.write_text('not-json-secret' if kind == 'invalid_json' else 'x'*(1024*1024+1))
    proc = subprocess.run([sys.executable, 'scripts/judge_registry_writer.py', str(path)],
                          cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert proc.returncode == 2 and proc.stdout == ''
    assert 'Cannot read' in proc.stderr and 'not-json-secret' not in proc.stderr


def test_target_parent_is_checked_even_when_all_later_observations_agree(evidence):
    for stage, key in [('target', 'after'), ('sibling', 'before'),
                       ('sibling', 'after'), ('pull_request', 'after')]:
        evidence[stage][key]['parents'] = ['c'*40]
    assert judge(evidence)['verdict'] == 'inconclusive'


@pytest.mark.parametrize('field,value', [
    ('pull_request.files.items.0.additions', True),
    ('pull_request.files.items.0.deletions', False),
    ('pull_request.files.items.0.additions', 1.0),
    ('pull_request.files.items.0.deletions', 0.0),
    ('pull_request.files.status', 200.0),
    ('credential_control.status', 200.0),
])
def test_numeric_observations_require_json_integers(evidence, field, value):
    set_value(evidence, field, value)
    assert judge(evidence)['verdict'] == 'inconclusive'


def test_boolean_repository_selection_is_not_numeric_id_one(evidence):
    evidence['expected_identity']['repository_id'] = 1
    evidence['credential_control']['repository_id'] = 1
    evidence['credential_control']['repository_selection'] = [True]
    assert judge(evidence)['verdict'] == 'inconclusive'


@pytest.mark.parametrize('variant', ['duplicate_origin', 'duplicate_nested_identity',
                                     'NaN', 'Infinity', '-Infinity'])
def test_cli_rejects_ambiguous_or_nonstandard_json(tmp_path, evidence, variant):
    raw = json.dumps(evidence)
    if variant == 'duplicate_origin':
        raw = raw.replace('"branch_origin": "app"',
                          '"branch_origin": "operator", "branch_origin": "app"')
    elif variant == 'duplicate_nested_identity':
        raw = raw.replace('"identity": "installation-token"',
                          '"identity": "operator", "identity": "installation-token"', 1)
    else:
        raw = raw[:-1] + ', "unobserved": ' + variant + '}'
    path = tmp_path/'ambiguous.json'
    path.write_text(raw)
    proc = subprocess.run([sys.executable, 'scripts/judge_registry_writer.py', str(path)],
                          cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert proc.returncode == 2 and proc.stdout == ''
    assert proc.stderr == 'Cannot read a valid bounded evidence JSON document.\n'
