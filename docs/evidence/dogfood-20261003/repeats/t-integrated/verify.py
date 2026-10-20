"""Audit saved T observations; never contact a cluster or execute a deployment."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent


def read(name):
    return json.loads((HERE / name).read_text())


def seconds(end, start):
    return round((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds(), 3)


def component(name):
    text = (HERE / name).read_text()
    return text.split('paragraph: Deploy a prepared image', 1)[1].split('paragraph: Deployment logs', 1)[0]


def capture(name):
    record = read(name)
    assert record['exit_code'] == 0
    return json.loads(record['stdout'])


def audit():
    events = {(e['label'], e['event']): e['at'] for e in
              map(json.loads, (HERE / 'ui-events.jsonl').read_text().splitlines())}
    baseline = capture('before/deployment-before.json')
    uid = baseline['metadata']['uid']
    assert uid == '8567c751-fc44-4e28-b63e-e21af534661f'
    rows = []
    for label, tag, expected, namespace in [
        ('normal1', 'r1', 'succeeded', 'acme-dev-observability'),
        ('normal2', 'r0', 'succeeded', 'acme-dev-observability'),
        ('normal3', 'r1', 'succeeded', 'acme-dev-observability'),
        ('failure1', 'missing-r1', 'failed', 'acme-dev-observability'),
        ('failure2', 'missing-r1', 'failed', 'acme-dev-observability'),
        ('restore', 'r0', 'succeeded', 'acme-dev-observability'),
        ('denial1', 'r0', 'failed', 'globex-dev-observability'),
        ('denial2', 'r0', 'failed', 'globex-dev-observability'),
    ]:
        run = read(label + '-run.json')
        image = 'localhost:5001/orders-api-dogfood:' + tag
        request = run['state']['request']
        assert request == dict(service_name='orders-api-dogfood', namespace=namespace,
                               image_uri=image, replicas=2, environment='dev',
                               model='onprem-executor', provider='onprem')
        assert run['status'] == expected and run['claims'] == 1
        assert run['tool_calls'] == {'deploy_to_cluster': 1}
        call = next(e for e in run['state']['events'] if e['type'] == 'tool_call')
        assert call['args']['image_uri'] == image and call['args']['replicas'] == 2
        assert call['args']['namespace'] == namespace
        result = next(e for e in run['state']['events'] if e['type'] == 'tool_result')
        if label.startswith('denial'):
            assert 'Forbidden' in json.dumps(result)
            assert 'system:serviceaccount:acme-dev-observability:platform-agent' in json.dumps(result)
            text = component(label + '-reload.txt')
            assert run['request_id'] in text and 'strong: failed' in text and 'Forbidden' in text
        row = dict(label=label, request_id=run['request_id'], status=expected,
                   deployment_id=run['record']['deployment_id'], claims=run['claims'],
                   tool_calls=run['tool_calls'], server_seconds=run['acceptance_to_persistence_sec'])
        if expected == 'succeeded':
            observation = read(label + '-observation.json')
            deployment = read(label + '-deployment.json')
            health = read(label + '-health.json')
            assert observation['uid'] == uid and observation['replicas'] == 2
            assert observation['image'] == image and len(health) == 2
            assert all('"GET /healthz HTTP/1.1" 200' in v for v in health.values())
            assert deployment['metadata']['uid'] == uid
            assert deployment['spec']['replicas'] == deployment['status']['readyReplicas'] == 2
            row.update(revision=observation['revision'], click_to_health_seconds=seconds(
                observation['healthy_observed_at'], events[(label, 'confirm_click')]))
        rows.append(row)
    for label in ('normal2', 'normal3'):
        run = read(label + '-run.json')
        assert run['request_id'] in component(label + '-before-loss.txt')
        assert 'strong: running' in component(label + '-before-loss.txt')
        assert run['request_id'] in component(label + '-after-loss.txt')
        assert 'strong: succeeded' in component(label + '-after-loss.txt')
        states = run['state']
        assert datetime.fromisoformat(events[(label, 'reload_during_submission')]).timestamp() < states['updated_at']
    recoveries = []
    prior_spec = read('normal3-deployment.json')['spec']
    for n in (1, 2):
        failed = capture(f'failing{n}/deployment-before.json')
        assert failed['metadata']['uid'] == uid
        assert failed['spec']['template']['spec']['containers'][0]['image'].endswith(':missing-r1')
        objects = capture(f'failing{n}/replicasets-pods.json')['items']
        revision = failed['metadata']['annotations']['deployment.kubernetes.io/revision']
        sets = [o for o in objects if o['kind'] == 'ReplicaSet'
                and o['metadata'].get('annotations', {}).get('deployment.kubernetes.io/revision') == revision
                and any(a.get('uid') == uid and a.get('controller') for a in o['metadata'].get('ownerReferences', []))]
        assert len(sets) == 1
        current_pods = [o for o in objects if o['kind'] == 'Pod' and not o['metadata'].get('deletionTimestamp')
                        and any(a.get('uid') == sets[0]['metadata']['uid'] for a in o['metadata'].get('ownerReferences', []))]
        assert current_pods and any(s.get('state', {}).get('waiting', {}).get('reason') in ('ErrImagePull', 'ImagePullBackOff')
                                    for p in current_pods for s in p['status'].get('containerStatuses', []))
        restored = capture(f'restored{n}/deployment-before.json')
        assert restored['metadata']['uid'] == uid and restored['spec'] == prior_spec
        run = read(f'recovery{n}-run.json')
        assert run['status'] == 'failed'  # The original request history remains failed.
        deploys = [r for r in run['activity_rows'] if r['PK'] == 'DEPLOY']
        assert [r['status'] for r in deploys] == ['failed', 'rolled-back']
        assert len({r['deployment_id'] for r in deploys}) == 1
        acts = [r for r in run['activity_rows'] if r['PK'] == 'ACTIVITY']
        assert [r['tool_calls'] for r in acts] == [['deploy_to_cluster'], ['rollback_deployment']]
        text = (HERE / f'recovery{n}-reload.txt').read_text()
        assert run['record']['deployment_id'] in text and 'rolled-back' in text
        health = read(f'recovery{n}-health.json')
        assert len(health) == 2 and all('"GET /healthz HTTP/1.1" 200' in s for s in health.values())
        observed = read(f'recovery{n}-observation.json')
        recoveries.append({'label': f'recovery{n}', 'deployment_id': run['record']['deployment_id'],
                           'revision': observed['revision'], 'click_to_health_seconds': seconds(
                               observed['healthy_observed_at'], events[(f'recovery{n}', 'confirm_rollback_click')]),
                           'failed_ui_observation_to_health_seconds': seconds(
                               observed['healthy_observed_at'], events[(f'failure{n}', 'failed_ui_observed')])})
    final = capture('final/deployment-before.json')
    assert final['metadata']['uid'] == uid and final['spec'] == baseline['spec']
    assert read('denial-before-resources.json')['items'] == read('denial-after-resources.json')['items'] == []
    unchanged = read('denial-own-unchanged.json')
    assert unchanged['spec'] == final['spec'] and unchanged['metadata']['generation'] == final['metadata']['generation']
    denials = read('credential-denials.json')['records']
    assert len(denials) == 4 and all(r['exit_code'] != 0 and 'Forbidden' in r['stderr'] for r in denials)
    approvals = read('approval-records.json')
    assert approvals['pending_total'] == 0 and approvals['actual_newline_count'] == 1
    assert len(approvals['records']) == 2
    for index, pair in enumerate(approvals['records'], 1):
        a, incident = pair['approval'], pair['incident']
        assert a['status'] == 'rejected' and a['rejection_reason'] == incident['rejection_reason']
        assert incident['approval_id'] == a['approval_id'] and incident['executed_actions'] == []
        text = (HERE / f'approval{index}-detail-reload.txt').read_text()
        assert a['approval_id'] in text and incident['incident_id'] in text
        assert 'Executed actions — 0' in text and 'Remediation rejected' in text
    missing = read('missing-scope.json')
    assert len(missing['results']) == 2 and missing['dispatch_attempts'] == []
    assert all(r['refused'] for r in missing['results'])
    normal = [r for r in rows if r['label'].startswith('normal')]
    return {'at': datetime.now(timezone.utc).isoformat(), 'candidate': 'O/v15',
            'rows': rows, 'recoveries': recoveries,
            'normal_click_to_health_median_seconds': statistics.median(r['click_to_health_seconds'] for r in normal),
            'normal_server_median_seconds': statistics.median(r['server_seconds'] for r in normal),
            'normal_repeats': 3, 'loss_repeats': 2, 'failure_recovery_repeats': 2,
            'ui_credential_denials': 2, 'api_read_denials': 2, 'api_create_dry_run_denials': 2,
            'synthetic_approval_rejections': 2, 'unscoped_live_runner_refusals': 2,
            'final_uid': uid, 'final_revision': final['metadata']['annotations']['deployment.kubernetes.io/revision'],
            'full_spec_restored': True, 'missing_scope_dispatches': 0,
            'r3_overall': 'incomplete: diagnosis criteria still fail',
            'limits': ['Same executable sources, explicitly switched to the existing tenant identity for denial and restored afterward.',
                       'Local single-user scenario; shared deployer tenant isolation is not established.',
                       'r0/r1 are cached tags of the same digest, not different application binaries.',
                       'Pod liveness HTTP200 is not external service/dependency health; no outage/MTTR claim.',
                       'Approval fixtures bypassed alert ingestion and model analysis; they prove the rejection path only.',
                       'No new diagnostic-model responses; S/O semantic failures remain.']}


if __name__ == '__main__':
    result = audit()
    result['evidence_sha256'] = {str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in HERE.rglob('*') if p.is_file() and p.name not in ('verification.json',)
                               and '__pycache__' not in str(p)}
    (HERE / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('rows', 'recoveries', 'limits', 'evidence_sha256')}, ensure_ascii=False))
