"""Offline reconciliation of preserved HTTP observations; no credentials/network."""
import copy
from datetime import datetime,timedelta
import hashlib
import json
from pathlib import Path

import pytest

from src.agents.platform.writer_reconciliation import reconcile_ref_read

ROOT=Path(__file__).resolve().parents[1]/'experiments/phase5-writer/retry-20260913'
REVIEW=(ROOT/'ref-read-review.json').read_bytes()
PIN=hashlib.sha256(REVIEW).hexdigest()

@pytest.fixture
def bundle():return json.loads((ROOT/'ref-read-observations.json').read_text())


def judge(bundle,**kw):
    return reconcile_ref_read(REVIEW,bundle,expected_review_sha256=PIN,
        as_of=kw.pop('as_of',bundle['author']['observed_at']),max_age_seconds=kw.pop('max_age_seconds',300),**kw)


def test_saved_observations_reconcile_without_promoting_the_failed_execution(bundle):
    before=copy.deepcopy(bundle);result=judge(bundle)
    assert result['verdict']=='consistent_partial',result
    assert result['original_execution_state']=='STOPPED'
    assert result['original_failure']=={'stage':'create_pr','reason':'TypeError'}
    assert result['writer_success_verified'] is result['retry_authorized'] is result['live_verified'] is False
    assert result['gaps']==['issue_app_field_null','installation_identity_pr_files_unobserved',
        'historical_request_credential_not_independently_proven','offline_records_not_authenticated']
    assert bundle==before and judge(bundle)==result
    assert result['author_observed_at']!=result['execution_started_at']


@pytest.mark.parametrize('path,value',[
    ('execution.scope','different-run'),
    ('execution.app_id',999),
    ('execution.repository_id',True),
    ('execution.review_sha256','0'*64),
    ('execution.state','CONSISTENT'),
    ('mint.permissions.contents','write'),
    ('mint.repository_ids',[999]),
    ('mint.credential_fingerprint','unavailable'),
    ('operations.write_target.receipt.attempt_id','0'*32),
    ('operations.create_pr.event.event_id','0'*32),
    ('operations.write_target.capture.request.body.branch','other-branch'),
    ('operations.create_pr.capture.reply.status',200),
    ('execution.cleanup','UNRESOLVED'),
    ('execution.revoked_token_get_status',200),
    ('execution.branch_seed.main','0'*40),
    ('execution.target_snapshot.parents',[]),
    ('execution.final_snapshot.files.platform/tenants/globex.yaml.sha','0'*40),
    ('execution.protected_after.main.commit','0'*40),
    ('execution.token_new_ref.identity','operator'),
    ('operations.write_sibling.capture.reply.permission_denial_verified',False),
    ('operations.write_sibling.event.message_class','rate_limit_error'),
    ('operator_pr.number',True),
    ('operator_pr.draft',False),
    ('operator_pr.files',[{'filename':'different-file'}]),
    ('operator_pr.head_sha','0'*40),
    ('author.author_evidence.app.id',999),
    ('author.author_evidence.bot.id',999),
    ('author.author_evidence.sources.bot.identity','installation-token'),
    ('author.author_evidence.writer_success_verified',True),
    ('author.author_evidence.issue_app_field','matching'),
    ('author.files',[]),
    ('author.refs.main','0'*40),
    ('author.calls',[]),
    ('author.write_requests',1),
    ('author.installation_token_mints',True),
])
def test_conflicting_partial_or_cross_run_records_never_reconcile(bundle,path,value):
    # Dots inside fixture filenames are preserved by choosing the longest key.
    cursor=bundle;remaining=path
    while remaining not in cursor:
        key=next(key for key in cursor if remaining.startswith(key+'.'))
        remaining=remaining[len(key)+1:];cursor=cursor[key]
    cursor[remaining]=value
    result=judge(bundle)
    assert result['verdict']=='inconclusive',result
    assert result['writer_success_verified'] is False and result['retry_authorized'] is False


@pytest.mark.parametrize('part',['author','mint','operator_pr','operations'])
def test_missing_evidence_does_not_fill_from_another_summary(bundle,part):
    bundle.pop(part)
    result=reconcile_ref_read(REVIEW,bundle,expected_review_sha256=PIN,as_of='2026-09-13T12:00:00Z',max_age_seconds=300)
    assert result['verdict']=='inconclusive'


@pytest.mark.parametrize('case',['stale','future','naive','reversed','token_expired','float_age','duplicate_attempt'])
def test_reconciliation_time_and_attempt_boundaries(bundle,case):
    stamp=datetime.fromisoformat(bundle['author']['observed_at']);options={}
    if case=='stale':options['as_of']=(stamp+timedelta(seconds=301)).isoformat()
    if case=='future':options['as_of']=(stamp-timedelta(seconds=1)).isoformat()
    if case=='naive':options['as_of']='2026-09-13T12:00:00'
    if case=='reversed':bundle['operations']['create_pr']['intent']['created_at']='2026-09-12T00:00:00Z'
    if case=='token_expired':bundle['mint']['expires_at']=bundle['execution']['observed_at']
    if case=='float_age':options['max_age_seconds']=300.0
    if case=='duplicate_attempt':
        value=bundle['operations']['create_ref']['intent']['attempt_id']
        bundle['operations']['write_target']['intent']['attempt_id']=value
    result=judge(bundle,**options)
    assert result['verdict']=='inconclusive',result


def test_actual_sibling_tree_change_is_a_boundary_failure_even_when_a_summary_says_denied(bundle):
    bundle['execution']['sibling_snapshot']['files']['platform/tenants/globex.yaml']['sha']='0'*40
    result=judge(bundle)
    assert result['verdict']=='boundary_failure'
    assert result['writer_success_verified'] is False


def test_the_review_is_bound_by_bytes_not_a_caller_supplied_status(bundle):
    changed=REVIEW+b'\n'
    result=reconcile_ref_read(changed,bundle,expected_review_sha256=PIN,
        as_of=bundle['author']['observed_at'],max_age_seconds=300)
    assert result['reason']=='review_digest_mismatch'


def test_successful_sibling_http_response_is_not_relabelled_as_denial(bundle):
    record=bundle['operations']['write_sibling']
    record['event']['http_status']=200
    record['capture']['reply']['status']=200
    record['capture']['attempt']['http_status']=200
    bundle['execution']['attempts']['write_sibling']['http_status']=200
    assert judge(bundle)['verdict']=='boundary_failure'


@pytest.mark.parametrize('case',['valid','missing','duplicate_keys','oversized','wrong_review'])
def test_cli_uses_bounded_strict_input_and_never_returns_writer_success(bundle,tmp_path,capsys,case):
    from scripts.reconcile_registry_writer import main
    path=tmp_path/'input.json'
    content=json.dumps(bundle)
    if case=='missing':bundle.pop('mint');content=json.dumps(bundle)
    if case=='duplicate_keys':content='{"schema_version":1,"schema_version":2}'
    if case=='oversized':content='x'*262145
    path.write_text(content)
    code=main([str(path),'--review',str(ROOT/'ref-read-review.json'),
        '--review-sha256','0'*64 if case=='wrong_review' else PIN,
        '--as-of',bundle['author']['observed_at'],'--max-age-seconds','300'])
    output=json.loads(capsys.readouterr().out)
    assert code==(0 if case=='valid' else 2)
    assert output['writer_success_verified'] is output['live_verified'] is output['retry_authorized'] is False
    assert 'App token' not in json.dumps(output)
