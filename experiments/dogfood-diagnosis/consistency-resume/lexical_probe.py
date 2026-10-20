"""Distinguish image-name shortcuts from lifecycle observations; no prompt change.

New synthetic controls change only image references in the matching object specs.
Historical raw cases remain unmodified. The original literal-name responses are
already recorded in replay-after; these controls do not replace their failures.
"""
from copy import deepcopy
from datetime import datetime
import asyncio

import replay

original_cases=replay.cases

def controls(module):
    rows=[]
    for row in original_cases(module):
        if row['id'] not in {'positive-complete','s-both-failing-consistent','positive-recovery'}:
            continue
        row=deepcopy(row);row['id'] += '-neutral-image'
        raw=row['raw'];d,objects=raw['deployment'],raw['objects']
        mapping={'app:missing':'registry.local/orders:release','app:good':'registry.local/orders:stable'}
        def change(spec):
            for c in spec.get('containers',[]):
                c['image']=mapping.get(c.get('image'),c.get('image'))
        change(d['spec']['template']['spec'])
        for obj in objects:
            change(obj.get('spec',{}).get('template',{}).get('spec',{}) if obj['kind']=='ReplicaSet' else obj.get('spec',{}))
        old=row['tool_result']['evidence']
        sources=[{**s,'sha256':module.digest(value)} for s,value in zip(old['sources'],[d,objects])]
        facts=module.summarize_deployment(d,objects,context=old['target']['context'],namespace=d['metadata']['namespace'],name=d['metadata']['name'],
            sources=sources,as_of=datetime.fromisoformat(old['as_of']),window_start=datetime.fromisoformat(old['window_start']))
        assert facts['rollout_complete']==old['rollout_complete'] and facts['recovery']==old['recovery']
        assert facts['rollout_counts']==old['rollout_counts'] and facts['investigation']==old['investigation']
        row['tool_result']={'ok':True,'evidence':facts,'diagnostic_observations':module.pod_waiting_observations(facts,objects)}
        rows.append(row)
    return rows

if __name__=='__main__':
    replay.cases=controls
    asyncio.run(replay.main())
