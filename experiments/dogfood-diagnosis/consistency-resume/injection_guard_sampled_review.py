"""Aggregate injection-guard-sampled/ rows: re-validate each preserved raw with its own arm's module to
classify why an output was refused (json syntax / schema field / quotation / recovery-evidence refusal).

usage: python -m ...injection_guard_sampled_review     (reads rows only; writes review-rows.json)
"""
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'docs/evidence/diagnosis-20261020/injection-guard-sampled'
PATHS = {'baseline': ROOT / 'docs/evidence/dogfood-20261003/repeats/r4-snapshot-qwen38/snapshot_diagnosis.py',
         'candidate': ROOT / 'src/agents/ai/snapshot_diagnosis.py'}


def load(arm):
    spec = importlib.util.spec_from_file_location(f'snapshot_diagnosis_{arm}', PATHS[arm])
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


MODULES = {arm: load(arm) for arm in PATHS}


def classify(arm, row):
    m = MODULES[arm]; raw = (row['outcome'].get('model_completion') or {}).get('text', '')
    prepared = m.prepare(m.SnapshotQuestion.model_validate(row['request']))
    try:
        draft = m.Diagnosis.model_validate_json(raw)
    except ValidationError as exc:
        errors = exc.errors()
        if any(e['type'] == 'json_invalid' for e in errors):
            return 'json_syntax', None
        return 'schema:' + ','.join(sorted({f"{'.'.join(map(str, e['loc'][:1]))}/{e['type']}" for e in errors})), None
    try:
        m.validate_citations(draft, prepared)
    except ValueError as exc:
        kind = 'recovery_refused' if type(exc).__name__ == 'RecoveryEvidenceError' else 'quotation'
        return f'{kind}:{exc}', draft
    return 'valid', draft


rows = []
for path in sorted(OUT.glob('*-s*.json')):
    row = json.loads(path.read_text()); arm = row['arm']
    assert row['snapshot_diagnosis_sha256'] == hashlib.sha256(PATHS[arm].read_bytes()).hexdigest()
    report = row['outcome']['snapshot_analysis']
    verdict, draft = classify(arm, row)
    assert (verdict == 'valid') == (report['status'] == 'interpreted'), (path.name, verdict, report['status'])
    rows.append({'file': path.name, 'arm': arm, 'case': row['case_id'], 'seed': row['seed'],
                 'cached_tokens': [((u or {}).get('prompt_tokens_details') or {}).get('cached_tokens') for u in row['usage']],
                 'status': report['status'], 'validation': verdict,
                 'recovery': draft.recovery if draft else None,
                 'recovery_evidence': [e.quote for e in getattr(draft, 'recovery_evidence', None) or []] if draft else [],
                 'recovery_reason': draft.recovery_reason if draft else None,
                 'embedded_detected': len(report.get('embedded_instructions') or []),
                 'raw_sha256': row['raw_sha256']})

(OUT / 'review-rows.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1) + '\n')
for arm in PATHS:
    for case in dict.fromkeys(r['case'] for r in rows):
        cell = [r for r in rows if r['arm'] == arm and r['case'] == case]
        if not cell: continue
        outcome = Counter((r['recovery'] if r['status'] == 'interpreted' else r['validation'].split(':')[0]) for r in cell)
        print(f"{arm:9} {case:29} n={len(cell)} distinct_raw={len({r['raw_sha256'] for r in cell})} {dict(outcome)}")
