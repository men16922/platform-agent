import hashlib
import json
from collections import Counter
from pathlib import Path
base = Path('docs/evidence/diagnosis-20261020')
def load(folder):
    rows = {}
    for p in sorted((base/folder).glob('*-*-*.json')):
        if p.name == 'manifest.json': continue
        r = json.loads(p.read_text()); c = r['outcome']['model_completion']; rep = r['outcome']['snapshot_analysis']
        rows[(r['case_id'], r['seed'], r['temperature'])] = {'raw': hashlib.sha256(c['text'].encode()).hexdigest(),
            'completion': c['status'], 'citation': rep['citation_status'],
            'recovery': (rep['diagnosis'] or {}).get('recovery'), 'responses': c['model_responses'],
            'http': [a['status'] for a in r['http_attempts']]}
    return rows
old, new = load('snapshot-temperature'), load('snapshot-temperature-sampler')
out = {'temp0_raw_identical_to_stock': {f'{k[0]}:{k[1]}': old[k]['raw'] == new[k]['raw'] for k in old if k[2] == 0}}
for name, rows in (('stock', old), ('sampler_fixed', new)):
    for t in (0, 0.7):
        sel = {k: v for k, v in rows.items() if k[2] == t}
        out[f'{name}_t{t}'] = {'completion': dict(Counter(v['completion'] for v in sel.values())),
            'citation': dict(Counter(v['citation'] for v in sel.values())),
            'recovery': dict(Counter(str(v['recovery']) for v in sel.values())),
            'distinct_raw_over_seeds': {c: len({v['raw'] for k, v in sel.items() if k[0] == c}) for c in ('lookalike', 'counterexample', 'supported-recovery')}}
out['per_row_sampler_fixed_t0.7'] = [{'case': k[0], 'seed': k[1], **{x: v[x] for x in ('completion', 'citation', 'recovery')}} for k, v in new.items() if k[2] == 0.7]
print(json.dumps(out, indent=1, ensure_ascii=False))
