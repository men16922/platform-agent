"""Replay saved Q/S raw observations; no network, cluster or model access."""
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path

from src.agents.ai.deployment_evidence import digest, summarize_deployment
from tests.test_deployment_evidence import NOW, snapshot

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'docs/evidence/dogfood-20261003/repeats'


def inputs():
    result = []
    for name in ('failing', 'restored'):
        folder = BASE / 'q-revision-window' / name
        dep = json.loads((folder / 'deployment-before.json').read_text())
        related = json.loads((folder / 'replicasets-pods.json').read_text())
        manifest = json.loads((folder / 'manifest.json').read_text())
        result.append((f'q-{name}', json.loads(dep['stdout']), json.loads(related['stdout'])['items'],
                       dep['completed_at'], related['completed_at'], manifest['window_start'], manifest['at']))
    cases = json.loads((BASE / 's-proposal-enum-replay/cases.json').read_text())
    raw = next(c['raw_synthetic_fixture'] for c in cases if c['id'] == 'both-revisions-failing-consistent')
    d, objects = raw['deployment'], raw['objects']
    result.append(('s-both-failing-consistent', deepcopy(d), deepcopy(objects), *[NOW.isoformat()] * 4))
    d = deepcopy(d); d['status'].update(readyReplicas=1, availableReplicas=1)
    result.append(('s-original-contradiction', d, deepcopy(objects), *[NOW.isoformat()] * 4))
    d, objects = snapshot()
    result.append(('positive-recovery', deepcopy(d), deepcopy(objects), *[NOW.isoformat()] * 4))
    d['status']['replicas'] = 1
    result.append(('aggregate-complete-pod-failed', deepcopy(d), deepcopy(objects), *[NOW.isoformat()] * 4))
    d, objects = snapshot()
    d['status']['replicas'] = 1
    objects = [objects[0], objects[2]]
    objects[0]['status']['availableReplicas'] = 1
    objects[1]['status'] = {'conditions': [{'type':'Ready', 'status':'True'}],
        'containerStatuses': [{'name':'orders', 'ready':True, 'state':{'running':{}}}]}
    result.append(('positive-complete', d, objects, *[NOW.isoformat()] * 4))
    return result


def measure():
    rows = []
    for cid, d, objects, d_at, o_at, start, end in inputs():
        facts = summarize_deployment(d, objects, context='recorded-local-context',
            namespace=d['metadata']['namespace'], name=d['metadata']['name'],
            sources=[{'source_id':'deployment', 'sha256':digest(d), 'observed_at':d_at},
                     {'source_id':'replicasets-pods', 'sha256':digest(objects), 'observed_at':o_at}],
            as_of=datetime.fromisoformat(end), window_start=datetime.fromisoformat(start))
        rows.append({'id':cid, 'deployment_sha256':digest(d), 'objects_sha256':digest(objects),
            'facts':facts})
    return {'source_sha256':hashlib.sha256((ROOT/'src/agents/ai/deployment_evidence.py').read_bytes()).hexdigest(),
            'scope':'Historical raw replay and separately identified synthetic controls; no live observations or model calls.',
            'cases':rows}


if __name__ == '__main__':
    import sys
    out = Path(sys.argv[1])
    if out.exists():
        raise FileExistsError(out)
    report = measure()
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    for row in report['cases']:
        f = row['facts']
        print(row['id'], 'complete=',f['rollout_complete'], 'current=',(f['current'] or {}).get('health_basis'),
              'recovery=',f['recovery']['status'], 'consistency=',f.get('observation_consistency','MISSING'))
